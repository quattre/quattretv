"""
Piezas horarias del archivo de storage1 a las que les falta un trozo.

get.php recorta cada pieza (archive/<id>/AAAAMMDD-HH.mpg) por bytes: el
segundo s de la hora lo busca en s/3600 del fichero. Si el grabador se corto
un rato, la pieza es mas corta y todo lo que se pide en ella sale en otro
sitio: el 02/11/2026 la de las 08 de Hollywood solo tenia de 08:45 a 09:00
(una cuarta parte), y "Como entrenar a tu dragon 3", de las 08:57:23, se abria
a las 08:58:36, ya empezada. Pasa a menudo: en dos dias, 43 canales tenian
alguna hora corta, y a las 18 del 01/11 casi todos. Y aunque este entera, en
los canales de bitrate variable los bytes no van parejos con el reloj.

La hora de verdad la dice la propia señal: el PTS del video avanza con el
reloj y sigue de una pieza a la siguiente mientras no se corte. Aqui se mide
cada pieza ya cerrada (unos KB de cada punto) y se guarda que segundo de get.php
corresponde a que segundo de la hora. Se mide en Celery y no al pedir el
enlace: get.php consulta el token a esta misma web y, con los 4 workers
ocupados esperandose, se bloquearia.
"""
import logging
from datetime import timedelta

import requests
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

VUELTA = 2 ** 33 / 90000   # el PTS da la vuelta cada ~26,5 h
PASO = 120                 # cada cuanto se mide (con 300 se desviaba hasta 34 s)
GUARDAR = 8 * 24 * 3600    # el archivo guarda 7 dias


def _clave(archivo_id, hora):
    return 'pieza:%s:%s' % (archivo_id, hora.strftime('%Y%m%d-%H'))


def _dif(a, b):
    """Segundos de PTS de a a b, con la vuelta."""
    d = (b - a) % VUELTA
    return d - VUELTA if d > VUELTA / 2 else d


def _buscar_pts(d):
    """Primer PTS de video en unos bytes de MPEG-TS."""
    i = d.find(b'\x47')
    while 0 <= i < len(d) - 188 and d[i + 188] != 0x47:
        i = d.find(b'\x47', i + 1)
    if i < 0:
        return None
    for pos in range(i, len(d) - 187, 188):
        p = d[pos:pos + 188]
        if p[0] != 0x47 or not p[1] & 0x40:
            continue
        af = (p[3] >> 4) & 3
        if af == 2:
            continue
        e = p[4 + (1 + p[4] if af == 3 else 0):]
        if len(e) >= 14 and e[:3] == b'\x00\x00\x01' and 0xE0 <= e[3] <= 0xEF and e[7] & 0x80:
            b = e[9:14]
            return (((b[0] >> 1) & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | b[4] >> 1) / 90000
    return None


class Medidor:
    def __init__(self, base, archivo_id, token):
        self.base, self.archivo_id, self.token = base, archivo_id, token
        self.pedidas = 0

    def pts(self, hora, segundo):
        """PTS del segundo `segundo` (el de get.php) de la pieza, o None si no
        existe. Un fallo de red se deja subir: se vuelve a intentar luego."""
        self.pedidas += 1
        url = '%s?ch_id=%s&filename=%s.mpg&start=%d&duration=1&token=%s' % (
            self.base, self.archivo_id, hora.strftime('%Y%m%d-%H'), segundo, self.token)
        with requests.get(url, stream=True, timeout=(3, 10)) as r:
            if r.status_code == 404:
                return None
            r.raise_for_status()
            datos = b''
            for trozo in r.iter_content(65536):
                datos += trozo
                pts = _buscar_pts(datos)
                if pts is not None or len(datos) > 1 << 20:
                    return pts
        return None

    def medir(self, hora):
        """Lo que se guarda de una pieza: {'p': [[segundo get.php, segundo de
        la hora], ...], 'fin': llega al final de la hora}, o {'x': motivo} si
        no se puede saber. Se mide aunque tenga la hora entera: en los canales
        de bitrate variable (Syfy, La 2) el segundo 2100 de get.php era el
        30:43 de la hora, no el 35:00."""
        a = self.pts(hora, 0)
        z = self.pts(hora, 3599) if a is not None else None
        if a is None or z is None:
            return {'x': 'sin pieza'}
        puntos = [(0, a)] + [(n, self.pts(hora, n)) for n in range(PASO, 3600, PASO)] + [(3599, z)]
        puntos = [(n, p) for n, p in puntos if p is not None]
        # Para saber que hora es cada PTS hace falta una punta que siga sin
        # corte con la pieza de al lado.
        siguiente = self.pts(hora + timedelta(hours=1), 0)
        if siguiente is not None and 0 <= _dif(z, siguiente) <= 5:
            reloj = [(n, 3600 - _dif(p, siguiente)) for n, p in puntos]
            reloj.reverse()
            fin = True
        else:
            anterior = self.pts(hora - timedelta(hours=1), 3599)
            if anterior is None or not 0 <= _dif(anterior, a) <= 5:
                return {'x': 'sin ancla'}
            reloj = [(n, _dif(anterior, p) - 1) for n, p in puntos]
            fin = False
        # Desde la punta buena, mientras el reloj vaya en orden: tras otro
        # corte de PTS ya no se sabe que hora es.
        buenos = [reloj[0]]
        for n, s in reloj[1:]:
            if not -5 <= s <= 3605 or (s >= buenos[-1][1]) == fin:
                break
            buenos.append((n, s))
        buenos.sort()
        return {'p': [[n, round(s, 1)] for n, s in buenos], 'fin': fin}


def medir_pendientes(horas=168, presupuesto=3000):
    """Mide las piezas ya cerradas que aun no se han medido, de la mas nueva a
    la mas vieja, hasta `presupuesto` peticiones a get.php."""
    from apps.channels.models import Channel
    from apps.stalker_api.storage_views import archive_storage, id_en_archivo, make_archive_token

    st = archive_storage()
    if not st:
        return 0
    base = st.build_url('get.php', public=True)
    ahora = timezone.localtime().replace(minute=0, second=0, microsecond=0)
    canales = list(Channel.objects.filter(
        has_catchup=True, is_active=True, archive_hls_since__isnull=True))
    # Por carpeta y no por canal: la de una señal que cambio de canal la
    # comparten dos (Channel.archivo_anterior) y se mide una vez.
    medidores = {}
    cortas = 0
    for atras in range(1, horas + 1):
        hora = ahora - timedelta(hours=atras)
        for c in canales:
            carpeta = id_en_archivo(c, hora)
            clave = _clave(carpeta, hora)
            if cache.get(clave) is not None:
                continue
            if carpeta not in medidores:
                medidores[carpeta] = Medidor(base, carpeta, make_archive_token(0, c.id))
            try:
                medida = medidores[carpeta].medir(hora)
            except requests.RequestException as exc:
                logger.warning('pieza %s %s: %s', c.name, hora, exc)
                continue
            cache.set(clave, medida, GUARDAR)
            if medida.get('p') and medida['p'][0][1] > 60:
                cortas += 1
                logger.info('pieza corta %s %s: empieza en el %s', c.name, hora.strftime('%d/%m %H'), medida['p'][0][1])
            if sum(m.pedidas for m in medidores.values()) >= presupuesto:
                return cortas
    return cortas


def corregir(archivo_id, inicio, duracion):
    """
    (hora de la pieza, segundo para get.php, duracion para get.php) de lo que
    empieza a `inicio` (hora local) y dura `duracion` segundos de verdad.

    get.php cuenta la duracion pieza a pieza en sus segundos, asi que lo que
    sobra o falta en la primera se suma a la duracion.
    """
    hora = inicio.replace(minute=0, second=0, microsecond=0)
    t = inicio.minute * 60 + inicio.second
    medida = cache.get(_clave(archivo_id, hora))
    if not medida or not medida.get('p'):
        return hora, t, duracion
    p = medida['p']
    # Entre punto y punto se reparte a partes iguales: hasta 17 s de error en
    # Syfy, el de bitrate mas variable. Sin margen hacia atras a proposito: los
    # saltos de 30 s del deco tambien pasan por aqui y se quedarian en 20.
    if t <= p[0][1]:
        # Lo de antes no se grabo: desde lo primero que hay.
        n = p[0][0]
    elif t >= p[-1][1]:
        if not medida['fin']:
            # La pieza se corta antes de acabar la hora: sigue en la siguiente.
            return hora + timedelta(hours=1), 0, max(60, duracion - (3600 - t))
        n = p[-1][0]
    else:
        for (n0, s0), (n1, s1) in zip(p, p[1:]):
            if s0 <= t <= s1:
                n = n0 + (n1 - n0) * (t - s0) / (s1 - s0) if s1 > s0 else n0
                break
    n = int(n)
    return hora, n, max(60, duracion + t - n)
