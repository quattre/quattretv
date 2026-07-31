"""
Celery tasks for EPG updates.
"""
import gzip
import logging
import zlib

import requests
import xmltodict
from celery import shared_task
from django.utils import timezone
from datetime import datetime

logger = logging.getLogger(__name__)


@shared_task
def update_epg_source(source_id):
    """Update EPG from a single source."""
    from .models import EpgSource, Program
    from apps.channels.models import Channel

    try:
        source = EpgSource.objects.get(id=source_id)
    except EpgSource.DoesNotExist:
        logger.error(f"EPG source {source_id} not found")
        return

    logger.info(f"Updating EPG from: {source.name}")

    try:
        response = requests.get(source.url, timeout=180)
        response.raise_for_status()

        # Parse XMLTV
        data = xmltodict.parse(descomprimir(response.content))
        tv_data = data.get('tv', {})

        # Get channel mapping. epg_id is blank (not null) when unmapped, so an
        # isnull filter would map every channel to the empty key.
        channels_map = {
            c.epg_id: c for c in Channel.objects.exclude(epg_id='')
        }

        # Process programs
        programs_to_create = []
        programmes = tv_data.get('programme', [])

        if not isinstance(programmes, list):
            programmes = [programmes]

        for prog in programmes:
            channel_id = prog.get('@channel')
            if channel_id not in channels_map:
                continue

            channel = channels_map[channel_id]

            # Parse times
            start = parse_xmltv_time(prog.get('@start'))
            stop = parse_xmltv_time(prog.get('@stop'))

            if not start or not stop:
                continue

            programs_to_create.append(Program(
                channel=channel,
                epg_id=channel_id,
                title=xmltv_text(prog.get('title')),
                description=xmltv_text(prog.get('desc')),
                start_time=start,
                end_time=stop,
                category=xmltv_text(prog.get('category')),
                episode_title=xmltv_text(prog.get('sub-title')),
            ))

        if programs_to_create:
            _replace_programs(programs_to_create)
            logger.info(f"Created {len(programs_to_create)} programs")

        source.last_update = timezone.now()
        source.save(update_fields=['last_update'])

    except Exception as e:
        logger.error(f"Error updating EPG from {source.name}: {e}")
        raise


def descomprimir(contenido):
    """
    Casi todas las fuentes buenas sirven el XMLTV comprimido.

    Antes se le pasaba el .gz tal cual al parser y reventaba con 'not
    well-formed', así que las dos fuentes con más cobertura no se podían usar.
    Se mira la firma del fichero y no la extensión, porque hay servidores que
    sirven .gz sin que la URL lo diga.
    """
    if contenido[:2] == b'\x1f\x8b':
        return gzip.decompress(contenido)
    if contenido[:2] == b'\x78\x9c':  # zlib a secas
        return zlib.decompress(contenido)
    return contenido


def _replace_programs(programs):
    """
    Replace the programs covered by this feed.

    Deleting only the future (and re-inserting the whole file) duplicated every
    past program on each run, so instead we clear exactly the window each
    channel brings and re-insert it.
    """
    from .models import Program

    windows = {}
    for prog in programs:
        start, end = windows.get(prog.channel_id, (prog.start_time, prog.end_time))
        windows[prog.channel_id] = (
            min(start, prog.start_time),
            max(end, prog.end_time),
        )

    for channel_id, (start, end) in windows.items():
        Program.objects.filter(
            channel_id=channel_id,
            start_time__gte=start,
            start_time__lte=end,
        ).delete()

    Program.objects.bulk_create(programs, batch_size=1000)


@shared_task
def update_all_epg_sources():
    """Update all active EPG sources."""
    from .models import EpgSource

    sources = EpgSource.objects.filter(is_active=True, auto_update=True)
    for source in sources:
        update_epg_source.delay(source.id)


@shared_task
def cleanup_old_programs():
    """Delete programs older than the longest catchup window we serve."""
    from .models import Program
    from apps.channels.models import Channel
    from datetime import timedelta
    from django.db.models import Max

    max_hours = Channel.objects.filter(is_active=True).aggregate(
        h=Max('timeshift_hours')
    )['h'] or 0
    # Keep at least a week so the archive always has its guide.
    keep_hours = max(max_hours, 24 * 7)

    cutoff = timezone.now() - timedelta(hours=keep_hours)
    deleted, _ = Program.objects.filter(end_time__lt=cutoff).delete()
    logger.info(f"Deleted {deleted} old programs")


def xmltv_text(node):
    """XMLTV nodes can be a string, a dict with #text, or a list of either."""
    if node is None:
        return ''
    if isinstance(node, list):
        node = node[0] if node else None
        if node is None:
            return ''
    if isinstance(node, dict):
        return node.get('#text', '') or ''
    return str(node)


def parse_xmltv_time(time_str):
    """
    Parse XMLTV time format: 'YYYYMMDDHHmmss +0200'.

    The offset matters: dropping it and localising to the server timezone
    shifted the whole guide by one or two hours.
    """
    if not time_str:
        return None

    parts = str(time_str).strip().split()
    if not parts:
        return None

    try:
        dt = datetime.strptime(parts[0][:14], '%Y%m%d%H%M%S')
    except ValueError:
        return None

    if len(parts) > 1:
        offset = parts[1]
        try:
            sign = -1 if offset[0] == '-' else 1
            minutes = int(offset[1:3]) * 60 + int(offset[3:5])
            return dt.replace(tzinfo=timezone.get_fixed_timezone(sign * minutes))
        except (ValueError, IndexError):
            pass

    # No offset in the feed: assume it is already in the portal timezone.
    return timezone.make_aware(dt)
