"""
Celery tasks that drive the external recorders.

Nothing is recorded here: we only decide *what* record1 should be recording and
push the order to it. The storage answers back on the stream_recorder callback.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# How far ahead we hand a recording to the storage. dumpstream takes a
# start_delay, so we can queue it early and let the recorder wait.
DISPATCH_LEAD = timedelta(minutes=10)

# Grace period before we give up waiting for the 'ended' callback.
CALLBACK_GRACE = timedelta(minutes=15)


def pick_storage(role='records'):
    """Pick an active storage able to take client recordings."""
    from .models import StorageServer, StorageRole

    roles = [StorageRole.BOTH]
    roles.append(StorageRole.RECORDS if role == 'records' else StorageRole.ARCHIVE)
    return StorageServer.objects.filter(is_active=True, role__in=roles).first()


@shared_task
def dispatch_due_recordings():
    """Send every recording that is about to start to its storage server."""
    from .models import Recording, RecordingStatus
    from . import storage_client

    now = timezone.now()
    storage = pick_storage('records')
    if not storage:
        logger.warning('No active storage server for client recordings')
        return 0

    sent = 0
    pending = Recording.objects.filter(
        status=RecordingStatus.SCHEDULED
    ).select_related('channel')

    for recording in pending:
        start = recording.actual_start_time
        end = recording.actual_end_time

        if start > now + DISPATCH_LEAD:
            continue

        if end <= now:
            recording.status = RecordingStatus.FAILED
            recording.error_message = 'La grabación caducó sin llegar a enviarse'
            recording.save(update_fields=['status', 'error_message'])
            continue

        source = recording.channel.multicast_url
        if not source:
            recording.status = RecordingStatus.FAILED
            recording.error_message = (
                'El canal no tiene origen multicast configurado (multicast_url)'
            )
            recording.save(update_fields=['status', 'error_message'])
            continue

        start_delay = max(0, int((start - now).total_seconds()))
        duration = int((end - max(start, now)).total_seconds())

        try:
            filename = storage_client.start_recording(
                storage, source, recording.id, duration, start_delay
            )
        except storage_client.StorageError as exc:
            logger.error('Recording %s failed: %s', recording.id, exc)
            recording.status = RecordingStatus.FAILED
            recording.error_message = str(exc)
            recording.save(update_fields=['status', 'error_message'])
            continue

        recording.storage = storage
        recording.filename = filename if isinstance(filename, str) else ''
        recording.status = RecordingStatus.RECORDING
        recording.duration = duration
        recording.save(update_fields=[
            'storage', 'filename', 'status', 'duration'
        ])
        sent += 1

    return sent


@shared_task
def apply_recording_rules():
    """Turn series rules into concrete recordings using the guide."""
    from apps.epg.models import Program
    from .models import Recording, RecordingRule, RecordingStatus

    now = timezone.now()
    horizon = now + timedelta(days=7)
    created = 0

    for rule in RecordingRule.objects.filter(is_active=True).select_related('channel'):
        programs = Program.objects.filter(
            start_time__gte=now, start_time__lte=horizon
        ).select_related('channel')

        if rule.channel_id:
            programs = programs.filter(channel_id=rule.channel_id)
        if rule.title_contains:
            programs = programs.filter(title__icontains=rule.title_contains)
        if rule.category:
            programs = programs.filter(category__iexact=rule.category)

        for program in programs:
            if not rule.matches_program(program):
                continue
            exists = Recording.objects.filter(
                user_id=rule.user_id, program=program
            ).exclude(status=RecordingStatus.CANCELLED).exists()
            if exists:
                continue

            Recording.objects.create(
                user_id=rule.user_id,
                channel=program.channel,
                program=program,
                title=program.title,
                description=program.description,
                start_time=program.start_time,
                end_time=program.end_time,
                pre_padding=rule.pre_padding,
                post_padding=rule.post_padding,
            )
            created += 1

        enforce_rule_quota(rule)

    return created


def enforce_rule_quota(rule):
    """Keep only the N newest completed recordings of a rule."""
    from .models import Recording, RecordingStatus
    from . import storage_client

    if not rule.keep_recordings:
        return

    completed = Recording.objects.filter(
        user_id=rule.user_id,
        channel_id=rule.channel_id or None,
        status=RecordingStatus.COMPLETED,
    ).order_by('-start_time')

    for old in completed[rule.keep_recordings:]:
        if old.storage and old.filename:
            try:
                storage_client.delete_recording_file(old.storage, old.filename)
            except storage_client.StorageError as exc:
                logger.warning('Could not delete %s: %s', old.filename, exc)
        old.delete()


@shared_task
def reconcile_recordings():
    """
    Close out recordings whose 'ended' callback never arrived.

    dumpstream calls us when it stops, but if the storage reboots mid-recording
    nobody would ever move the row out of 'recording'.
    """
    from .models import Recording, RecordingStatus

    now = timezone.now()
    stuck = 0

    for recording in Recording.objects.filter(status=RecordingStatus.RECORDING):
        if recording.actual_end_time + CALLBACK_GRACE > now:
            continue
        recording.status = RecordingStatus.COMPLETED
        recording.error_message = 'Cerrada sin callback del grabador'
        recording.save(update_fields=['status', 'error_message'])
        stuck += 1

    return stuck
