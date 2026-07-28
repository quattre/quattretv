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

from django.core import signing
from django.http import JsonResponse
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


def build_catchup_url(channel, start, duration, device=None):
    """
    Build the get.php URL that serves the archive for `start`.

    The archive is stored as hourly MPEG-TS pieces (YYYYMMDD-HH.mpg) and get.php
    slices them by byte offset, chaining consecutive files when the requested
    range crosses the hour.
    """
    storage = StorageServer.objects.filter(
        is_active=True, role__in=['archive', 'both']
    ).first()
    if not storage:
        return None

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


def archive_channels():
    """Channels we want the archive recorder to keep."""
    return Channel.objects.filter(
        is_active=True, has_catchup=True
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
