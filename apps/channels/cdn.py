"""
Estado de los canales en los CDN, y reinicio de los que se caen.

La comprobación no necesita acceso a la máquina: el CDN ya publica el HLS, y
ffmpeg reescribe la playlist cada pocos segundos mientras emite. Si esa
playlist lleva rato sin cambiar, el canal está parado. Con una sola petición
por canal se sabe.

El reinicio sí necesita entrar por SSH, y en el CDN hace falta una regla de
sudoers para que no pida contraseña (igual que la que ya existe para reiniciar
quattretv.service):

    quattre ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart ffmpeg-hls@*
"""
import email.utils
import logging
import re
import subprocess

import requests
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

TIMEOUT = 6
# ffmpeg reescribe la playlist en cada segmento; con segmentos de pocos
# segundos, un minuto sin tocarla ya es que no está emitiendo.
MAX_ANTIGUEDAD = 60
CACHE_SECONDS = 30
SSH_TIMEOUT = 20


def nombre_en_cdn(channel):
    """
    Nombre del canal en el CDN.

    Si no está puesto a mano se saca de la URL del stream, que tiene la forma
    http://cdnX:1500/hls/<nombre>/index.m3u8.
    """
    if channel.cdn_name:
        return channel.cdn_name

    match = re.search(r'/hls/([^/]+)/', channel.stream_url or '')
    return match.group(1) if match else ''


def estado_canal(channel, usar_cache=True):
    """
    Devuelve el estado de emisión de un canal.

    estado: 'emitiendo' | 'parado' | 'sin_cdn' | 'error'
    """
    if not channel.cdn:
        return {'estado': 'sin_cdn', 'detalle': 'Canal sin CDN asignado'}

    nombre = nombre_en_cdn(channel)
    if not nombre:
        return {'estado': 'sin_cdn', 'detalle': 'No se sabe el nombre en el CDN'}

    clave = f'cdn_estado:{channel.id}'
    if usar_cache:
        try:
            guardado = cache.get(clave)
            if guardado:
                return guardado
        except Exception:
            pass

    url = channel.cdn.playlist_url(nombre)
    resultado = _consultar(url)
    resultado['url'] = url
    resultado['nombre_cdn'] = nombre

    try:
        cache.set(clave, resultado, CACHE_SECONDS)
    except Exception:
        pass

    return resultado


def _consultar(url):
    try:
        respuesta = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return {'estado': 'error', 'detalle': f'No responde: {exc}'}

    if respuesta.status_code != 200:
        return {'estado': 'parado', 'detalle': f'HTTP {respuesta.status_code}'}

    modificado = respuesta.headers.get('Last-Modified')
    if not modificado:
        # Sin cabecera no se puede medir la antigüedad; al menos responde.
        return {'estado': 'emitiendo', 'detalle': 'Responde (sin Last-Modified)'}

    try:
        fecha = email.utils.parsedate_to_datetime(modificado)
    except (TypeError, ValueError):
        return {'estado': 'emitiendo', 'detalle': 'Responde'}

    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.utc)

    antiguedad = (timezone.now() - fecha).total_seconds()
    if antiguedad > MAX_ANTIGUEDAD:
        return {
            'estado': 'parado',
            'detalle': f'La playlist lleva {antiguedad / 60:.0f} min sin cambiar',
            'antiguedad': antiguedad,
        }

    return {
        'estado': 'emitiendo',
        'detalle': f'Al día ({antiguedad:.0f} s)',
        'antiguedad': antiguedad,
    }


def reiniciar_canal(channel):
    """
    Reinicia la unidad systemd del canal en su CDN.

    Devuelve (ok, mensaje). No lanza excepciones: esto se llama desde un botón.
    """
    if not channel.cdn:
        return False, 'El canal no tiene CDN asignado'
    if not channel.cdn.puede_reiniciar:
        return False, f'El CDN {channel.cdn.name} no tiene acceso SSH configurado'

    nombre = nombre_en_cdn(channel)
    if not nombre:
        return False, 'No se sabe el nombre del canal en el CDN'

    unidad = f'{channel.cdn.systemd_unit}{nombre}'
    orden = [
        'ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
        '-o', f'ConnectTimeout={TIMEOUT}',
        '-p', str(channel.cdn.ssh_port),
        f'{channel.cdn.ssh_user}@{channel.cdn.ssh_host}',
        f'sudo systemctl restart {unidad}',
    ]

    logger.info('Reiniciando %s en %s', unidad, channel.cdn.name)

    try:
        proceso = subprocess.run(
            orden, capture_output=True, text=True, timeout=SSH_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return False, 'El CDN no respondió a tiempo'
    except OSError as exc:
        return False, f'No se pudo ejecutar ssh: {exc}'

    if proceso.returncode != 0:
        error = (proceso.stderr or proceso.stdout or '').strip()[:300]
        return False, f'Fallo al reiniciar {unidad}: {error}'

    try:
        cache.delete(f'cdn_estado:{channel.id}')
    except Exception:
        pass

    return True, f'{unidad} reiniciado'


def estados_de(channels):
    """
    Estado de varios canales a la vez.

    En serie, 50 canales con timeout de 6 s podrían tardar minutos si el CDN no
    responde, y esto se pinta en una página web.
    """
    from concurrent.futures import ThreadPoolExecutor

    channels = list(channels)
    if not channels:
        return {}

    with ThreadPoolExecutor(max_workers=10) as pool:
        resultados = list(pool.map(estado_canal, channels))

    return {c.id: r for c, r in zip(channels, resultados)}


def resumen_cdn(cdn, estados=None):
    """Cuenta cuántos canales de un CDN están emitiendo y cuántos parados."""
    resumen = {'emitiendo': 0, 'parado': 0, 'error': 0, 'sin_cdn': 0, 'total': 0}
    canales = list(cdn.channels.filter(is_active=True))
    if estados is None:
        estados = estados_de(canales)

    for channel in canales:
        estado = estados.get(channel.id, {}).get('estado', 'error')
        resumen[estado] += 1
        resumen['total'] += 1
    return resumen
