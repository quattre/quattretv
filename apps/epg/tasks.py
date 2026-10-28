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
        #
        # Una lista y no un canal suelto: el mismo identificador puede estar en
        # mas de un canal, y con un diccionario simple el ultimo pisaba a los
        # demas y esos se quedaban sin guia, sin decir nada. Pasa siempre que se
        # lleva la misma cadena dos veces -- un HD y un SD, o una version sin la
        # franja de adultos.
        channels_map = {}
        for c in Channel.objects.exclude(epg_id=''):
            channels_map.setdefault(c.epg_id, []).append(c)

        # Process programs
        programs_to_create = []
        programmes = tv_data.get('programme', [])

        if not isinstance(programmes, list):
            programmes = [programmes]

        for prog in programmes:
            channel_id = prog.get('@channel')
            if channel_id not in channels_map:
                continue

            # Parse times
            start = parse_xmltv_time(prog.get('@start'))
            stop = parse_xmltv_time(prog.get('@stop'))

            if not start or not stop:
                continue

            for channel in channels_map[channel_id]:
                programs_to_create.append(Program(
                    channel=channel,
                    epg_id=channel_id,
                    title=xmltv_text(prog.get('title')),
                    description=xmltv_text(prog.get('desc')),
                    start_time=start,
                    end_time=stop,
                    category=xmltv_text(prog.get('category')),
                    episode_title=xmltv_text(prog.get('sub-title')),
                    icon=xmltv_imagen(prog.get('icon')),
                    year=xmltv_anio(prog.get('date')),
                ))

        if programs_to_create:
            programs_to_create = corregir_horas(source, programs_to_create)
        if programs_to_create:
            _replace_programs(programs_to_create)
            logger.info(f"Created {len(programs_to_create)} programs")
            # Los programas son nuevos: la hora real vista en la EIT se les
            # vuelve a apuntar.
            from . import eit
            eit.reaplicar({p.channel_id for p in programs_to_create},
                          min(p.start_time for p in programs_to_create),
                          max(p.end_time for p in programs_to_create))

        source.last_update = timezone.now()
        source.save(update_fields=['last_update'])

    except Exception as e:
        logger.error(f"Error updating EPG from {source.name}: {e}")
        raise


def corregir_horas(source, programas):
    """
    Si la fuente va desviada horas enteras en algun canal (la EIT lo dice: ver
    eit.desfases), se le corrige antes de guardarla. Lo hizo falta con el
    cambio de hora de octubre de 2026, y asi vale para los que vengan.
    """
    from . import eit
    from .models import Program
    try:
        cambios = eit.desfases(programas)
    except Exception as e:
        logger.error(f"EPG {source.name}: no se pudo mirar el desfase: {e}")
        return programas
    # Los canales en que esta fuente va mal sin arreglo no se toman de ella,
    # si ya tienen guia de otra; si no, mejor esta que ninguna.
    fuera = set()
    for canal, d in cambios.items():
        if d is None:
            suyos = [p for p in programas if p.channel_id == canal]
            if Program.objects.filter(channel_id=canal, start_time__gte=min(p.start_time for p in suyos),
                                      start_time__lte=max(p.start_time for p in suyos)).count() >= len(suyos) // 2:
                fuera.add(canal)
    programas = [p for p in programas if p.channel_id not in fuera]
    for p in programas:
        d = cambios.get(p.channel_id)
        if d:
            p.start_time += d
            p.end_time += d
    resumen = {}
    for canal, d in cambios.items():
        if d:
            resumen.setdefault(int(d.total_seconds() // 60), []).append(canal)
    if resumen or fuera:
        logger.warning(f"EPG {source.name}: horas corregidas con la EIT " +
                       ", ".join(f"{m:+d} min en {len(c)} canales" for m, c in resumen.items()) +
                       (f"; {len(fuera)} canales no se toman de esta fuente" if fuera else ""))
    return programas


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


def generico(titulo):
    from .completar import generico as _generico
    return _generico(titulo)


def mas_completa(nueva, vieja):
    from .completar import mas_completa as _mas_completa
    return _mas_completa(nueva, vieja)


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

    # Cada fuente trae cosas distintas del mismo programa: una la caratula,
    # otra la categoria, otra el año. Como la ultima en cargar pisaba a las
    # demas, de 9.413 programas de una semana solo 117 tenian categoria aunque
    # dos de las fuentes la traen. Lo que la nueva no trae se toma de lo que
    # habia en esa misma franja.
    anteriores = {}
    for channel_id, (start, end) in windows.items():
        franja = Program.objects.filter(
            channel_id=channel_id,
            start_time__gte=start,
            start_time__lte=end,
        )
        for viejo in franja.values('channel_id', 'start_time', 'title', *COMPLEMENTOS):
            anteriores[(viejo['channel_id'], viejo['start_time'])] = viejo
        franja.delete()

    for prog in programs:
        viejo = anteriores.get((prog.channel_id, prog.start_time))
        if viejo:
            # "Cine" o "Documental" no pisan el titulo de verdad que puso la
            # guia complementaria (ver completar.py).
            if generico(prog.title) and not generico(viejo['title']):
                prog.title = viejo['title']
            for campo in COMPLEMENTOS:
                if not getattr(prog, campo) and viejo[campo]:
                    setattr(prog, campo, viejo[campo])
            # La fuente trae "Cine" y la guia complementaria habia dejado
            # "Cine,Terror": sin esto el genero se perdia cada hora.
            if mas_completa(viejo['category'], prog.category):
                prog.category = viejo['category']

    Program.objects.bulk_create(programs, batch_size=1000)


# Lo que una fuente puede completar de otra. La hora real no: se vuelve a
# sacar de lo visto en la EIT (eit.reaplicar), y arrastrarla podia pegarsela
# a otro capitulo cuando la fuente cambia de hora.
COMPLEMENTOS = ('category', 'icon', 'description', 'episode_title', 'year',
                'season', 'episode')


@shared_task
def update_all_epg_sources():
    """Update all active EPG sources."""
    from .models import EpgSource

    sources = EpgSource.objects.filter(is_active=True, auto_update=True)
    for source in sources:
        update_epg_source.delay(source.id)


@shared_task
def completar_guia():
    """Rellena lo que le falta a la guia con la de dobleM (ver completar.py)."""
    from .completar import completar
    return completar()


@shared_task
def buscar_caratulas():
    """Caratulas de TMDB para lo del archivo que la guia trae sin imagen."""
    from apps.stalker_api.caratulas import buscar_las_que_faltan
    return buscar_las_que_faltan()


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

    from .models import ObservacionEit
    ObservacionEit.objects.filter(inicio__lt=timezone.now() - timedelta(days=4)).delete()


def xmltv_imagen(node):
    """
    La carátula del programa, que viene en <icon src="...">.

    Se estaba tirando, y la traen casi todos: 11.086 de 11.221 programas en
    TDTChannels y 32.760 de 33.854 en epgshare01. Sin esto la tele es una lista
    de texto.

    Igual que el resto de nodos XMLTV, puede venir suelto o repetido; si hay
    varios nos quedamos con el primero. Se descartan las que no son http(s)
    (alguna fuente mete rutas relativas que no llevan a ningún sitio) y las que
    no caben en el campo, que son siempre basura.
    """
    if isinstance(node, list):
        node = node[0] if node else None
    if not isinstance(node, dict):
        return ''

    src = (node.get('@src') or '').strip()
    if not src.startswith(('http://', 'https://')) or len(src) > 500:
        return ''
    return src


def xmltv_anio(node):
    """El año de <date>, que puede venir como '2019' o '20190314'."""
    texto = xmltv_text(node)[:4]
    if texto.isdigit() and 1900 <= int(texto) <= 2100:
        return int(texto)
    return None


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
