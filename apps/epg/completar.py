"""
Completar la guia con otra fuente, sin sustituirla.

Las fuentes que alimentan la guia traen bien las horas y los titulos, pero
poca cosa mas: imagen en el 71 % de los programas, y el tipo (cine, series,
infantil...) en casi ninguno. La guia de dobleM, gratuita y muy usada en
España, trae imagen en el 85 % y el genero y el año en casi todos, pero tiene
su propio formato y sus propias horas.

Asi que no se usa como guia: se cruza con la nuestra y solo rellena lo que
falta (caratula, tipo, año, descripcion, capitulo), programa a programa, por
canal, hora y titulo. Nuestras horas y titulos no se tocan nunca.

Cubre hoy y los 6 dias siguientes, asi que lo que se va a emitir llega ya
completo al archivo: en una semana, "Ultimos 7 dias" entero tiene imagen.
"""
import difflib
import gzip
import io
import logging
import re
import xml.etree.ElementTree as ET
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .matching import emparejar, normaliza

logger = logging.getLogger(__name__)

DOBLEM = 'https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml.gz'
MARGEN = 600            # segundos de diferencia de hora que se aceptan
COLOR = re.compile(r'\[/?COLOR[^\]]*\]')
# "Simon T5 E38 · ¿Hacemos las paces?" -> titulo, temporada, capitulo, nombre
TEMPORADA = re.compile(r'^(.*?)\s+T(\d+)(?:\s+E(\d+))?(?:\s+·\s+(.*))?$')
# "Cine,Programa de cine | 2020 | TP | ★6.2/10" -> genero y año
GENERO = re.compile(r'^\s*([^|]+?)\s*\|\s*(\d{4})\s*\|')

CAMPOS = ('icon', 'category', 'year', 'description', 'episode_title', 'season', 'episode')

# Nuestros canales que en dobleM se llaman de otra manera.
ALIAS = {
    'FDF': 'Factoría de Ficción',
    'Syfy': 'SciFi HD',
    'Star': 'STAR Channel HD',
    'Hollywood': 'Canal Hollywood HD',
    'Castilla La Mancha TV': 'CMM TV',
    'Extremadura TV': 'Canal Extremadura',
    '13TV': 'TRECE',
    '7 Valencia TV': '7teleValencia',
    'Canal 33': 'El 33 Catalunya',
}

# Titulos que no dicen que es: La 2 pone "Cine" o "Documental" y dobleM trae
# el de verdad ("Dodge, ciudad sin ley"). En una tarjeta de "Ultimos 7 dias"
# un "Cine" no sirve de nada.
GENERICOS = {'cine', 'documental', 'documentales', 'pelicula', 'serie', 'series',
             'programa por determinar', 'por determinar', 'programacion'}


def generico(titulo):
    return plano(titulo).strip(' .') in GENERICOS


def limpio(texto):
    return COLOR.sub('', texto or '').strip()


def plano(texto):
    from apps.stalker_api.semana import plano as _plano
    return _plano(texto)


def parecido(a, b):
    """Si dos titulos son del mismo programa, aunque cada guia lo escriba a su manera."""
    if not a or not b:
        return False
    if a == b or a.startswith(b) or b.startswith(a):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.6


def _texto(elemento, etiqueta):
    """El primero que haya: dobleM pone primero el texto sin colores."""
    for hijo in elemento.findall(etiqueta):
        if hijo.text and hijo.text.strip():
            return limpio(hijo.text)
    return ''


def leer_programa(el):
    from .tasks import parse_xmltv_time

    titulo = _texto(el, 'title')
    datos = {'titulo': titulo, 'season': None, 'episode': None, 'episode_title': ''}
    m = TEMPORADA.match(titulo)
    if m:
        datos['titulo'] = m.group(1).strip()
        datos['season'] = int(m.group(2))
        datos['episode'] = int(m.group(3)) if m.group(3) else None
        datos['episode_title'] = (m.group(4) or '').strip()

    sub = _texto(el, 'sub-title')
    m = GENERO.match(sub)
    datos['category'] = m.group(1).split(',')[0].strip() if m else ''
    anio = int(m.group(2)) if m else None
    datos['year'] = anio if anio and 1900 <= anio <= 2100 else None

    # La primera linea es la sinopsis; las demas son pais, reparto...
    descr = _texto(el, 'desc').split('\n')[0]
    datos['description'] = descr.lstrip('· ').strip()

    icono = el.find('icon')
    src = (icono.get('src') or '').strip() if icono is not None else ''
    datos['icon'] = src if src.startswith(('http://', 'https://')) and len(src) <= 500 else ''

    datos['ini'] = parse_xmltv_time(el.get('start'))
    datos['plano'] = plano(datos['titulo'])
    return datos


def leer_fuente(url, canales):
    """
    {canal nuestro: [programas de la fuente]}. Solo se guardan los canales que
    tenemos y lo que cae en la ventana que interesa, que el fichero trae 643
    canales y 80.000 programas.
    """
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    contenido = r.content
    if contenido[:2] == b'\x1f\x8b':
        contenido = gzip.decompress(contenido)
    # dobleM deja sin cerrar alguna <icon src="..."> (89 de 71.000 el dia que
    # se probo) y el fichero entero dejaba de ser XML valido.
    contenido = re.sub(rb'</icon>', b'', contenido)
    contenido = re.sub(rb'(<icon [^>]*?)\s*/?>', rb'\1 />', contenido)

    ahora = timezone.now()
    desde, hasta = ahora - timedelta(hours=36), ahora + timedelta(days=8)
    nombres, suyos, resultado = {}, None, {}
    for _, el in ET.iterparse(io.BytesIO(contenido), events=('end',)):
        if el.tag == 'channel':
            for nombre in el.findall('display-name'):
                if nombre.text and nombre.text.strip():
                    nombres.setdefault(normaliza(nombre.text), (el.get('id', ''), nombre.text.strip()))
            nombres.setdefault(normaliza(el.get('id', '')), (el.get('id', ''), el.get('id', '')))
            el.clear()
        elif el.tag == 'programme':
            if suyos is None:
                # Los canales van todos antes que el primer programa.
                suyos = {}
                for canal in canales:
                    hallado = (canal.name in ALIAS and emparejar(ALIAS[canal.name], nombres)) or \
                        emparejar(canal.name, nombres) or \
                        (canal.epg_id and emparejar(canal.epg_id, nombres))
                    if hallado:
                        suyos.setdefault(hallado[0], []).append(canal)
            mios = suyos.get(el.get('channel'))
            if mios:
                datos = leer_programa(el)
                if datos['ini'] and desde <= datos['ini'] <= hasta:
                    for canal in mios:
                        resultado.setdefault(canal, []).append(datos)
            el.clear()
    return resultado


def completar(url=None, guardar=True):
    """
    Rellena lo que le falta a nuestra guia. Devuelve cuantos programas ha
    tocado. Con guardar=False solo cuenta, para probar una fuente nueva.
    """
    from apps.channels.models import Channel
    from .models import Program

    url = url or settings.QUATTRETV.get('EPG_COMPLETAR') or DOBLEM
    canales = list(Channel.objects.filter(is_active=True, is_radio=False))
    fuente = leer_fuente(url, canales)

    ahora = timezone.now()
    tocados = 0
    for canal, suyos in fuente.items():
        programas = Program.objects.filter(
            channel=canal,
            start_time__gte=ahora - timedelta(hours=36),
            start_time__lte=ahora + timedelta(days=8),
        )
        cambiados = []
        for p in programas:
            sin_titulo = generico(p.title)
            if not sin_titulo and all(getattr(p, campo) not in ('', None) for campo in CAMPOS):
                continue
            nuestro = plano(p.title)
            mejor = None
            for d in suyos:
                if abs((d['ini'] - p.start_time).total_seconds()) <= MARGEN and \
                        (sin_titulo or parecido(nuestro, d['plano'])):
                    mejor = d
                    break
            if not mejor:
                continue
            cambio = False
            if sin_titulo and mejor['titulo'] and not generico(mejor['titulo']):
                p.title = mejor['titulo'][:500]
                cambio = True
            for campo in CAMPOS:
                if getattr(p, campo) in ('', None) and mejor[campo] not in ('', None):
                    setattr(p, campo, mejor[campo])
                    cambio = True
            if cambio:
                cambiados.append(p)
        if cambiados and guardar:
            Program.objects.bulk_update(cambiados, ('title',) + CAMPOS, batch_size=500)
        tocados += len(cambiados)
    logger.info('Guia completada con %s: %s programas en %s canales', url, tocados, len(fuente))
    return {'programas': tocados, 'canales': len(fuente)}
