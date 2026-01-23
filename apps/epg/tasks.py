"""
Celery tasks for EPG updates.
"""
import logging
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
        response = requests.get(source.url, timeout=60)
        response.raise_for_status()

        # Parse XMLTV
        data = xmltodict.parse(response.content)
        tv_data = data.get('tv', {})

        # Get channel mapping
        channels_map = {
            c.epg_id: c for c in Channel.objects.filter(epg_id__isnull=False)
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

            # Get title
            title_data = prog.get('title', {})
            if isinstance(title_data, dict):
                title = title_data.get('#text', '')
            else:
                title = str(title_data)

            # Get description
            desc_data = prog.get('desc', {})
            if isinstance(desc_data, dict):
                description = desc_data.get('#text', '')
            else:
                description = str(desc_data) if desc_data else ''

            # Get category
            cat_data = prog.get('category', {})
            if isinstance(cat_data, dict):
                category = cat_data.get('#text', '')
            elif isinstance(cat_data, list):
                category = cat_data[0].get('#text', '') if cat_data else ''
            else:
                category = str(cat_data) if cat_data else ''

            programs_to_create.append(Program(
                channel=channel,
                epg_id=channel_id,
                title=title,
                description=description,
                start_time=start,
                end_time=stop,
                category=category,
            ))

        # Delete old programs and insert new ones
        if programs_to_create:
            # Delete programs for updated channels from now onwards
            channel_ids = list(channels_map.values())
            Program.objects.filter(
                channel__in=channel_ids,
                start_time__gte=timezone.now()
            ).delete()

            Program.objects.bulk_create(programs_to_create, batch_size=1000)
            logger.info(f"Created {len(programs_to_create)} programs")

        source.last_update = timezone.now()
        source.save(update_fields=['last_update'])

    except Exception as e:
        logger.error(f"Error updating EPG from {source.name}: {e}")
        raise


@shared_task
def update_all_epg_sources():
    """Update all active EPG sources."""
    from .models import EpgSource

    sources = EpgSource.objects.filter(is_active=True, auto_update=True)
    for source in sources:
        update_epg_source.delay(source.id)


@shared_task
def cleanup_old_programs():
    """Delete programs older than 7 days."""
    from .models import Program
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=7)
    deleted, _ = Program.objects.filter(end_time__lt=cutoff).delete()
    logger.info(f"Deleted {deleted} old programs")


def parse_xmltv_time(time_str):
    """Parse XMLTV time format (YYYYMMDDHHmmss +0000)."""
    if not time_str:
        return None

    try:
        # Remove timezone info for simplicity
        time_str = time_str.split()[0]
        dt = datetime.strptime(time_str, '%Y%m%d%H%M%S')
        return timezone.make_aware(dt)
    except (ValueError, IndexError):
        return None
