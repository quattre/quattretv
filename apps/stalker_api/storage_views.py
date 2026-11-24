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
from django.http import HttpResponse, JsonResponse, QueryDict
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
    # Si hay una copia del grabador que nos obedece, esa: el get.php del de
    # Ministra valida los tokens con Ministra y no se tragaria los nuestros.
    return StorageServer.objects.filter(
        is_active=True, role__in=['archive', 'both']
    ).order_by('controlado_por_ministra').first()


def archivo_hls_para(device):
    """
    Si este aparato recibe el archivo de siempre en HLS (rangos.php y
    trozo.php de storage1) en vez de por get.php. Se decide en el .env,
    ARCHIVO_HLS: ids de aparato y/o tipos ('android', 'lg', 'mag'...) separados
    por comas, o 'todos'; con '-' delante, un id o un usuario que se excluye.
    Vacio = nadie, como antes.
    """
    if not device:
        return False
    fichas = {x.strip() for x in settings.QUATTRETV.get('ARCHIVO_HLS', '').split(',') if x.strip()}
    # '-algo' lo quita: un id de aparato o un usuario ('-googlereview', la
    # cuenta con la que revisa Google Play, que ve la app sin estas secciones).
    quitar = {x[1:] for x in fichas if x.startswith('-')}
    usuario = getattr(getattr(device, 'user', None), 'username', '')
    if str(device.id) in quitar or (usuario and usuario in quitar):
        return False
    return 'todos' in fichas or str(device.id) in fichas or device.device_type in fichas


def por_https(device):
    """
    Si los trozos del archivo y de las grabaciones le van a este aparato por
    https, a traves de iptv2 (deploy/nginx/archivo_https.sh), en vez de directos
    de storage1/record1 por http. La app de Android solo admite https; el deco
    sigue por http directo, que su reproductor viejo no abre https.
    """
    return bool(settings.QUATTRETV.get('HLS_POR_IPTV2')) and bool(device) and device.device_type != 'mag'


def base_https(ruta):
    """Por donde salen por https: HLS_URL (iptv1, el nombre definitivo) o PUBLIC_URL."""
    q = settings.QUATTRETV
    return f"{(q.get('HLS_URL') or q.get('PUBLIC_URL', '')).rstrip('/')}/{ruta}"


def id_en_archivo(channel, momento=None):
    """
    Con que numero esta guardado el canal en el archivo de storage1.

    El archivo en MPEG-TS lo empezo Ministra y sus carpetas llevan el id interno
    de alli (archive/<id>/). Se sigue usando para no perder ni una hora al
    cambiar; un canal nuevo, que Ministra no tuvo nunca, usa el id de aqui.
    Con `momento`, lo de antes de que el canal cambiara de señal esta en la
    carpeta de la señal vieja (Channel.archivo_anterior).
    """
    if (momento is not None and channel.archivo_anterior
            and channel.archivo_anterior_hasta and momento < channel.archivo_anterior_hasta):
        return channel.archivo_anterior
    return channel.ministra_id or channel.id


def almacen_archivo(channel, momento=None):
    """Grabador que tiene el archivo del canal en `momento` (Channel.archivo_en)."""
    if channel.archivo_en_id and id_en_archivo(channel, momento) == id_en_archivo(channel):
        return channel.archivo_en
    return archive_storage()


def clave_archivo(channel, momento=None):
    """
    Con que se busca el canal en ventanas_de_archivo() y en la cache de piezas.
    Las carpetas de storage1 van por su numero, como siempre; las de un
    grabador nuestro llevan delante el suyo, porque los numeros se repiten.
    """
    carpeta = id_en_archivo(channel, momento)
    if channel.archivo_en_id and carpeta == id_en_archivo(channel):
        return '%s:%s' % (channel.archivo_en_id, carpeta)
    return carpeta


def build_catchup_url(channel, start, duration, device=None):
    """
    Build the playback URL for the archive at `start`.

    Two formats coexist on purpose. A channel migrated to HLS keeps its old
    MPEG-TS pieces until they age out of the retention window, so anything
    recorded before `archive_hls_since` still has to be served the old way.
    That is what makes the migration seamless: no gap, no re-encoding of the
    past, and rolling back is just clearing the field.
    """
    storage = almacen_archivo(channel, start)
    if not storage:
        return None
    # Hora del directo -> hora en la señal que se graba (ver Channel.desfase_archivo).
    if channel.desfase_archivo:
        start = start + timedelta(minutes=channel.desfase_archivo)

    if channel.archive_hls_since and start >= channel.archive_hls_since:
        return build_hls_catchup_url(channel, start, duration, device)
    # El mismo archivo de siempre, en HLS por trozos de sus piezas horarias.
    if archivo_hls_para(device):
        return build_hls_catchup_url(channel, start, duration, device)

    return build_ts_catchup_url(storage, channel, start, duration, device)


def build_ts_catchup_url(storage, channel, start, duration, device=None):
    """
    Legacy path: the storage's get.php slices the hourly MPEG-TS pieces by byte
    offset, chaining consecutive files when the range crosses the hour.
    """
    from apps.stalker_api.piezas import corregir
    # Si a la pieza de esa hora le falta un trozo, el segundo de get.php no es
    # el de la hora (ver piezas.py).
    carpeta = id_en_archivo(channel, start)
    pieza, segundo, duration = corregir(clave_archivo(channel, start), timezone.localtime(start), int(duration))
    params = {
        'ch_id': carpeta,
        'filename': pieza.strftime('%Y%m%d-%H') + '.mpg',
        # get.php lee 'start'. Con otro nombre lo ignoraba y todo empezaba en
        # la hora en punto, no donde empieza el programa.
        'start': segundo,
        'duration': int(duration),
        'token': make_archive_token(device.id if device else 0, channel.id),
    }
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    # get.php esta al lado de rest.php (api_url): en record1 la de reproducir
    # es la carpeta de las grabaciones, no la del grabador.
    return storage.build_url('get.php') + '?' + query


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

# storage1 guarda los trozos del HLS del directo tal cual (deploy/storage/
# recoger_hls.py), uno por fichero con la hora UTC de su inicio en el nombre,
# asi que el indice sale del propio listado y no hay fichero de indice que
# mantener. El listado lo da lista.php, solo del rato que se pide: una semana
# entera son ~60.000 trozos por canal.
SEGMENT_NAME_FORMAT = '%Y%m%d-%H%M%S'
SEGMENT_SUFFIX = '.ts'
NOMINAL_SEGMENT_SECONDS = 10
INDEX_CACHE_SECONDS = 30


def parse_segment_name(name):
    """'20261123-164722.ts' (UTC) -> datetime aware, o None si no encaja."""
    if not name.endswith(SEGMENT_SUFFIX):
        return None
    try:
        naive = datetime.strptime(name[:-len(SEGMENT_SUFFIX)], SEGMENT_NAME_FORMAT)
    except ValueError:
        return None
    return naive.replace(tzinfo=dt_timezone.utc)


def fetch_segment_index(storage, channel, start, end):
    """
    Los trozos del archivo de un canal entre start y end (con un trozo de
    margen a cada lado), de lista.php del storage. Se guarda en cache un rato
    porque cada peticion del catchup iria si no al storage.
    """
    desde = (start - timedelta(seconds=2 * NOMINAL_SEGMENT_SECONDS)).astimezone(dt_timezone.utc)
    hasta = (end + timedelta(seconds=NOMINAL_SEGMENT_SECONDS)).astimezone(dt_timezone.utc)
    desde, hasta = desde.strftime(SEGMENT_NAME_FORMAT), hasta.strftime(SEGMENT_NAME_FORMAT)
    cache_key = f'archive_index:{storage.id}:{channel.id}:{desde}:{hasta}'
    try:
        cached = cache.get(cache_key)
    except Exception:
        # Que Redis esté caído no debe impedir ver el archivo, solo hace que se
        # consulte al storage cada vez.
        cached = None
    if cached is not None:
        return cached

    url = storage.build_url(f'{storage.archive_path}/lista.php')
    try:
        response = requests.get(url, params={'c': channel.id, 'desde': desde, 'hasta': hasta}, timeout=10)
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


def build_playlist(storage, channel, segments, start, end, https=False):
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

    base = (base_https(f'archivo_hls/{channel.id}/') if https
            else storage.build_url(f'{storage.archive_path}/{channel.id}/', public=True))
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


# ---------- El archivo de siempre en HLS, por trozos ----------

# indexar_archivo.py (deploy/storage) apunta en storage1 donde empieza cada
# rato de ~10 s dentro de las piezas horarias de dumpstream; rangos.php da ese
# indice y trozo.php entrega cada rato tal cual. Nada se convierte ni se copia.

def fetch_rangos(storage, carpeta, start, end):
    """Las piezas con sus trozos entre start y end, de rangos.php (en orden)."""
    desde, hasta = int(start.timestamp()) - 15, int(end.timestamp()) + 15
    reciente = end > timezone.now() - timedelta(minutes=5)
    cache_key = f'archivo_rangos:{storage.id}:{carpeta}:{desde}:{hasta}'
    try:
        cached = cache.get(cache_key)
    except Exception:
        cached = None
    if cached is not None:
        return cached
    url = storage.build_url(f'{storage.archive_path}/rangos.php')
    try:
        response = requests.get(url, params={'c': carpeta, 'desde': desde, 'hasta': hasta}, timeout=10)
        response.raise_for_status()
        piezas = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error('No se pudo leer el indice del archivo %s: %s', carpeta, exc)
        return []
    try:
        cache.set(cache_key, piezas, 10 if reciente else 300)
    except Exception:
        pass
    return piezas


def rangos_listos(channel, start, duration):
    """
    Si el indice de storage1 ya tiene el principio de este rato. Mientras se
    indexa lo atrasado (o en el ultimo minuto del directo) puede no estar:
    mejor decirlo que dar una lista vacia y dejar la pantalla en negro.
    """
    storage = almacen_archivo(channel, start)
    if not storage:
        return False
    if channel.desfase_archivo:      # como en build_catchup_url
        start = start + timedelta(minutes=channel.desfase_archivo)
    carpeta = id_en_archivo(channel, start)
    fin = start + timedelta(seconds=min(int(duration), 600))
    return any(pieza.get('t') for pieza in fetch_rangos(storage, carpeta, start, fin))


def playlist_de_rangos(storage, carpeta, piezas, start, end, https=False):
    """
    Lista .m3u8 de [start, end] con los trozos de las piezas. Si el rato llega
    hasta ahora no se cierra (EVENT): el aparato la vuelve a pedir y va
    encontrando lo que se graba.
    """
    from .piezas import _dif

    a, z = start.timestamp(), end.timestamp()
    base = (base_https('archivo_hls/trozo.php') if https
            else storage.build_url(f'{storage.archive_path}/trozo.php', public=True))
    cuerpo = []
    maximo = float(NOMINAL_SEGMENT_SECONDS)
    fin_pts = None
    for pieza in piezas:
        fichero = pieza.get('f', '')
        for inicio, pos, longitud, dur, pts in pieza.get('t', []):
            if inicio + dur <= a or inicio >= z:
                continue
            # La señal se corto (el grabador se reinicio): el reproductor tiene
            # que saber que el reloj del video salta.
            if fin_pts is not None and abs(_dif(fin_pts, pts)) > 1:
                cuerpo.append('#EXT-X-DISCONTINUITY')
            fin_pts = pts + dur
            maximo = max(maximo, dur)
            cuerpo.append('#EXT-X-PROGRAM-DATE-TIME:' + datetime.fromtimestamp(
                inicio, tz=dt_timezone.utc).isoformat(timespec='milliseconds'))
            cuerpo.append(f'#EXTINF:{dur:.3f},')
            cuerpo.append(f'{base}?c={carpeta}&f={fichero}&o={pos}&l={longitud}')
    abierta = end > timezone.now() - timedelta(minutes=1)
    if not cuerpo and not abierta:
        return None
    lineas = [
        '#EXTM3U',
        '#EXT-X-VERSION:3',
        f'#EXT-X-TARGETDURATION:{int(maximo + 0.999)}',
        '#EXT-X-MEDIA-SEQUENCE:0',
        '#EXT-X-PLAYLIST-TYPE:' + ('EVENT' if abierta else 'VOD'),
    ] + cuerpo
    if not abierta:
        lineas.append('#EXT-X-ENDLIST')
    return '\n'.join(lineas) + '\n'


def catchup_playlist(request, channel_id, start_ts, duration):
    """Serve the generated catchup playlist for a time window."""
    token = request.GET.get('token', '')
    try:
        datos = signing.loads(token, salt=ARCHIVE_TOKEN_SALT, max_age=ARCHIVE_TOKEN_TTL)
    except signing.BadSignature:
        return HttpResponse('Not valid token', status=403)
    from apps.devices.models import Device
    https = por_https(Device.objects.filter(id=datos.get('d') or 0).only('device_type').first())

    channel = Channel.objects.filter(id=channel_id, is_active=True).first()
    if not channel:
        return HttpResponse('Channel not found', status=404)

    start = datetime.fromtimestamp(int(start_ts), tz=dt_timezone.utc)
    end = start + timedelta(seconds=int(duration))

    if channel.archive_hls_since and start >= channel.archive_hls_since:
        storage = archive_storage()
        if not storage:
            return HttpResponse('No archive storage', status=503)
        playlist = build_playlist(
            storage, channel, fetch_segment_index(storage, channel, start, end), start, end, https
        )
    else:
        storage = almacen_archivo(channel, start)
        if not storage:
            return HttpResponse('No archive storage', status=503)
        carpeta = id_en_archivo(channel, start)
        playlist = playlist_de_rangos(
            storage, carpeta, fetch_rangos(storage, carpeta, start, end), start, end, https)
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
    ).exclude(origen_grabador='').order_by('number')


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
    if not storage or storage.controlado_por_ministra:
        return JsonResponse({'results': []})
    # Solo los canales que tiene asignados (Channel.archivo_en). Nuestra copia
    # de storage1 escribe en la misma carpeta que Ministra: si se le mandaran
    # tambien los que archiva Ministra, los dos escribirian el mismo fichero.
    canales = archive_channels().filter(archivo_en=storage)

    results = [
        {
            'ch_id': id_en_archivo(channel),
            'cmd': channel.origen_para_grabar,
            'parts_number': channel.timeshift_hours,
        }
        for channel in canales
    ]

    storage.last_sync = timezone.now()
    storage.save(update_fields=['last_sync'])

    return JsonResponse({'results': results})


@csrf_exempt
def stream_recorder_callback(request, rec_id):
    """
    dumpstream tells us when a client recording starts and ends.

    It sends the parameters as a plain HTTP request, so accept them from the
    query string or the body indistinctly. dumpstream manda un PUT con el
    cuerpo en form-urlencoded, y Django solo rellena request.POST en los POST:
    sin leer el cuerpo a mano, el aviso llegaba vacio y la grabacion se quedaba
    en "grabando" hasta que la cerraba reconcile_recordings.
    """
    params = {}
    params.update(request.GET.dict())
    params.update(request.POST.dict())
    if request.method in ('PUT', 'PATCH') and request.body:
        params.update(QueryDict(request.body).dict())

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
