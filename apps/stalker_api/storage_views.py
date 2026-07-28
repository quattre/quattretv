"""
Endpoints consumed by the recording servers (record1 / storage1).

These reproduce what Ministra offered them, so the boxes keep running exactly
as they do today — we only replace who answers:

  GET  {API_URL}tv_archive/{STORAGE_NAME}   -> list of channels to archive (pull)
  ANY  {API_URL}stream_recorder/{rec_id}    -> dumpstream callback (started/ended)
  GET  {PORTAL_URL}/server/api/chk_storage_token.php?token=
  GET  {PORTAL_URL}/server/api/chk_tmp_archive_link.php?token=
"""
import logging
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.channels.models import Channel
from apps.pvr.models import Recording, RecordingStatus, StorageServer

logger = logging.getLogger(__name__)

ARCHIVE_TOKEN_SALT = 'quattretv.archive.link'
ARCHIVE_TOKEN_TTL = 60 * 60 * 12  # 12h, enough for a long catchup session


def make_archive_token(device_id, channel_id):
    """Short-lived token the storage validates against chk_tmp_archive_link."""
    return signing.dumps(
        {'d': device_id, 'c': channel_id}, salt=ARCHIVE_TOKEN_SALT
    )


def archive_storage():
    return StorageServer.objects.filter(
        is_active=True, role__in=['archive', 'both']
    ).first()


def build_catchup_url(channel, start, duration, device=None):
    """
    Build the playback URL for the archive at `start`.

    Two formats coexist on purpose. A channel migrated to HLS keeps its old
    MPEG-TS pieces until they age out of the retention window, so anything
    recorded before `archive_hls_since` still has to be served the old way.
    That is what makes the migration seamless: no gap, no re-encoding of the
    past, and rolling back is just clearing the field.
    """
    storage = archive_storage()
    if not storage:
        return None

    if channel.archive_hls_since and start >= channel.archive_hls_since:
        return build_hls_catchup_url(channel, start, duration, device)

    return build_ts_catchup_url(storage, channel, start, duration, device)


def build_ts_catchup_url(storage, channel, start, duration, device=None):
    """
    Legacy path: the storage's get.php slices the hourly MPEG-TS pieces by byte
    offset, chaining consecutive files when the range crosses the hour.
    """
    local_start = timezone.localtime(start)
    params = {
        'ch_id': channel.id,
        'filename': local_start.strftime('%Y%m%d-%H') + '.mpg',
        'start_time': local_start.minute * 60 + local_start.second,
        'duration': int(duration),
        'token': make_archive_token(device.id if device else 0, channel.id),
    }
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    return storage.build_url('get.php', public=True) + '?' + query


def build_hls_catchup_url(channel, start, duration, device=None):
    """
    New path: we serve a generated playlist over the segments the recorder
    already wrote. No ffmpeg at playback time and no byte-offset guessing, so
    the seek lands where it should.
    """
    token = make_archive_token(device.id if device else 0, channel.id)
    return (
        f"{settings.QUATTRETV.get('PUBLIC_URL', '').rstrip('/')}"
        f"/storage_api/catchup/{channel.id}/{int(start.timestamp())}/"
        f"{int(duration)}.m3u8?token={token}"
    )


# ---------- Archivo en HLS ----------

# El grabador deja un segmento por trozo con el instante en el nombre
# (strftime de ffmpeg), asi que el indice se deduce del propio listado del
# directorio y no hace falta ningun fichero de indice que mantener.
SEGMENT_NAME_FORMAT = '%Y%m%d-%H%M%S'
SEGMENT_SUFFIX = '.ts'
NOMINAL_SEGMENT_SECONDS = 6
INDEX_CACHE_SECONDS = 30


def parse_segment_name(name):
    """'20260728-100006.ts' -> datetime aware, o None si no encaja."""
    if not name.endswith(SEGMENT_SUFFIX):
        return None
    try:
        naive = datetime.strptime(name[:-len(SEGMENT_SUFFIX)], SEGMENT_NAME_FORMAT)
    except ValueError:
        return None
    return timezone.make_aware(naive)


def fetch_segment_index(storage, channel):
    """
    List the archive segments of a channel.

    nginx serves the directory with `autoindex on; autoindex_format json;`, so
    this is a plain listing — no PHP and nothing to keep in sync. Cached
    briefly because every catchup request would otherwise hit the storage.
    """
    cache_key = f'archive_index:{storage.id}:{channel.id}'
    try:
        cached = cache.get(cache_key)
    except Exception:
        # Que Redis esté caído no debe impedir ver el archivo, solo hace que se
        # consulte al storage cada vez.
        cached = None
    if cached is not None:
        return cached

    url = storage.build_url(f'{storage.archive_path}/{channel.id}/', public=True)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        entries = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error('No se pudo listar el archivo de %s: %s', channel, exc)
        return []

    segments = []
    for entry in entries:
        name = entry.get('name', '') if isinstance(entry, dict) else str(entry)
        started = parse_segment_name(name)
        if started:
            segments.append((started, name))

    segments.sort()
    try:
        cache.set(cache_key, segments, INDEX_CACHE_SECONDS)
    except Exception:
        pass
    return segments


def build_playlist(storage, channel, segments, start, end):
    """Emit a finite (VOD) playlist covering [start, end]."""
    window = []
    for index, (seg_start, name) in enumerate(segments):
        if index + 1 < len(segments):
            seg_end = segments[index + 1][0]
        else:
            seg_end = seg_start + timedelta(seconds=NOMINAL_SEGMENT_SECONDS)
        if seg_end <= start or seg_start >= end:
            continue
        window.append((seg_start, (seg_end - seg_start).total_seconds(), name))

    if not window:
        return None

    base = storage.build_url(f'{storage.archive_path}/{channel.id}/', public=True)
    target = max(int(round(d)) for _, d, _ in window)

    lines = [
        '#EXTM3U',
        '#EXT-X-VERSION:3',
        f'#EXT-X-TARGETDURATION:{max(target, NOMINAL_SEGMENT_SECONDS)}',
        '#EXT-X-MEDIA-SEQUENCE:0',
        '#EXT-X-PLAYLIST-TYPE:VOD',
    ]
    for seg_start, seg_duration, name in window:
        lines.append('#EXT-X-PROGRAM-DATE-TIME:' + timezone.localtime(seg_start).isoformat())
        lines.append(f'#EXTINF:{seg_duration:.3f},')
        lines.append(base + name)
    lines.append('#EXT-X-ENDLIST')

    return '\n'.join(lines) + '\n'


def catchup_playlist(request, channel_id, start_ts, duration):
    """Serve the generated catchup playlist for a time window."""
    token = request.GET.get('token', '')
    try:
        signing.loads(token, salt=ARCHIVE_TOKEN_SALT, max_age=ARCHIVE_TOKEN_TTL)
    except signing.BadSignature:
        return HttpResponse('Not valid token', status=403)

    channel = Channel.objects.filter(id=channel_id, is_active=True).first()
    if not channel:
        return HttpResponse('Channel not found', status=404)

    storage = archive_storage()
    if not storage:
        return HttpResponse('No archive storage', status=503)

    start = datetime.fromtimestamp(int(start_ts), tz=dt_timezone.utc)
    end = start + timedelta(seconds=int(duration))

    playlist = build_playlist(
        storage, channel, fetch_segment_index(storage, channel), start, end
    )
    if not playlist:
        return HttpResponse('Archive not available for that time', status=404)

    return HttpResponse(playlist, content_type='application/vnd.apple.mpegurl')


def archive_channels():
    """
    Channels the legacy dumpstream recorder should keep archiving.

    A channel already migrated to HLS drops off this list so the old recorder
    stops being told to record it; otherwise both recorders would write the
    same channel and the archive would take twice the disk.
    """
    return Channel.objects.filter(
        is_active=True, has_catchup=True, archive_hls_since__isnull=True
    ).exclude(multicast_url='').order_by('number')


@csrf_exempt
def tv_archive_tasks(request, storage_name):
    """
    Task list pulled by tvarchivesync.php every few minutes.

    Answer shape is fixed by TvArchiveTasks::sync(): {"results": [...]}, each
    task carrying ch_id, cmd (udp://ip:port) and parts_number.
    """
    storage = StorageServer.objects.filter(
        name=storage_name, is_active=True
    ).first()
    if not storage or not storage.records_archive:
        return JsonResponse({'results': []})

    results = [
        {
            'ch_id': channel.id,
            'cmd': channel.multicast_url,
            'parts_number': channel.timeshift_hours,
        }
        for channel in archive_channels()
    ]

    storage.last_sync = timezone.now()
    storage.save(update_fields=['last_sync'])

    return JsonResponse({'results': results})


@csrf_exempt
def stream_recorder_callback(request, rec_id):
    """
    dumpstream tells us when a client recording starts and ends.

    It sends the parameters as a plain HTTP request, so accept them from the
    query string or the body indistinctly.
    """
    params = {}
    params.update(request.GET.dict())
    params.update(request.POST.dict())

    action = params.get('action', '')

    try:
        recording = Recording.objects.get(id=rec_id)
    except Recording.DoesNotExist:
        return JsonResponse({'result': False, 'error': 'Unknown recording'}, status=404)

    if action == 'started':
        recording.status = RecordingStatus.RECORDING
        recording.save(update_fields=['status'])

    elif action == 'ended':
        recording.status = RecordingStatus.COMPLETED
        if recording.filename and recording.storage:
            recording.stream_url = recording.storage.build_url(
                recording.filename, public=True
            )
        recording.save(update_fields=['status', 'stream_url'])

    else:
        # Archive mode reports the window it currently holds.
        logger.info('stream_recorder %s: %s', rec_id, params)

    return JsonResponse({'result': True})


def chk_storage_token(request):
    """Validate the Bearer token a storage received from us."""
    token = request.GET.get('token', '')
    valid = bool(token) and StorageServer.objects.filter(
        token=token, is_active=True
    ).exists()
    return JsonResponse({'result': valid})


def chk_tmp_archive_link(request):
    """Validate a catchup playback token issued by build_catchup_url()."""
    token = request.GET.get('token', '')
    try:
        signing.loads(token, salt=ARCHIVE_TOKEN_SALT, max_age=ARCHIVE_TOKEN_TTL)
    except signing.BadSignature:
        return JsonResponse({'result': False})
    return JsonResponse({'result': True})
