"""
Client for the Ministra-style storage servers (record1 / storage1).

We reuse the recorders that are already in production instead of writing our
own: they expose /rest.php (rewritten as <api_url>/<resource>/<identifiers>)
and run `dumpstream` against the channel multicast.

Wire format, taken from the storage's RESTRequest.php:
  - resource + identifiers travel in the path
  - POST=create, PUT=update, DELETE=delete, GET=get
  - the body is form-urlencoded (PHP parse_str), NOT json
  - auth is `Authorization: Bearer <token>`, which the storage validates by
    calling us back on chk_storage_token.php
"""
import logging

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 15


class StorageError(Exception):
    """The storage server refused or failed to run a command."""


def _request(storage, method, resource, identifiers=None, data=None):
    path = resource
    if identifiers:
        path = f"{resource}/{','.join(str(i) for i in identifiers)}"

    url = storage.build_url(path)
    headers = {}
    if storage.token:
        headers['Authorization'] = f'Bearer {storage.token}'

    logger.info("storage %s: %s %s %s", storage.name, method, url, data or '')

    try:
        response = requests.request(
            method, url, data=data or {}, headers=headers, timeout=TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise StorageError(f"{storage.name}: {exc}") from exc

    return _parse(storage, response)


def _parse(storage, response):
    """The storage answers with RESTResponse json; be lenient about its shape."""
    text = (response.text or '').strip()
    if not text:
        return None

    try:
        payload = response.json()
    except ValueError:
        return text

    if isinstance(payload, dict):
        error = payload.get('error')
        if error:
            raise StorageError(f"{storage.name}: {error}")
        for key in ('body', 'result', 'results', 'data'):
            if key in payload:
                return payload[key]
    return payload


def start_recording(storage, url, rec_id, duration, start_delay=0):
    """
    Ask the storage to record `duration` seconds of `url` (udp://ip:port).

    Returns the .mpg filename the recorder created.
    """
    return _request(storage, 'POST', 'recorder', data={
        'url': url,
        'rec_id': rec_id,
        'start_delay': max(0, int(start_delay)),
        'duration': int(duration),
    })


def stop_recording(storage, rec_id):
    """Stop a running recording (the storage SIGTERMs its dumpstream)."""
    return _request(storage, 'PUT', 'recorder', [rec_id], data={})


def update_stop_time(storage, rec_id, stop_time):
    """Extend/shorten a running recording without restarting it."""
    return _request(storage, 'PUT', 'recorder', [rec_id], data={
        'stop_time': int(stop_time),
    })


def delete_recording_file(storage, filename):
    return _request(storage, 'DELETE', 'recorder', [filename])


def create_playback_link(storage, media_file, media_id):
    """Symlink a finished recording into the device's NFS home so it can play."""
    return _request(storage, 'POST', 'remote_pvr', data={
        'media_file': media_file,
        'media_id': media_id,
    })


def stop_archive(storage, ch_id):
    """Stop the rolling archive of a channel on this storage."""
    return _request(storage, 'DELETE', 'tv_archive_recorder', [ch_id])
