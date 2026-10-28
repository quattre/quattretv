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
import bisect
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

# Desfases que se prueban por canal. dobleM se equivoca a veces de hora entera
# en algunos canales: tras el cambio de hora de octubre de 2026, AMC, Dark,
# Somos, Hollywood o XTRM iban una hora tarde (la EIT de la propia emision lo
# confirmaba) y no casaba ni una pelicula.
DESFASES = (0, -3600, 3600, -7200, 7200)

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
             'programa por determinar', 'por determinar', 'programacion',
             'multicine', 'sesion de tarde', 'el peliculon'}


def generico(titulo):
    return plano(titulo).strip(' .') in GENERICOS


def mas_completa(nueva, vieja):
    """Si la categoria nueva dice lo mismo y algo mas: "Cine" -> "Cine,Terror"."""
    n, v = plano(nueva), plano(vieja)
    return bool(n) and n != v and n.startswith(v)


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
    # Entero: "Cine,Terror,Suspense". El tipo decide la fila y el resto, las
    # filas por genero (ver apps/stalker_api/semana.py).
    datos['category'] = m.group(1).strip()[:100] if m else ''
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


def buscar(programa, suyos, inicios, desfase, sin_titulo):
    """El programa de la fuente que es este, con la hora corregida, o None."""
    momento = programa.start_time.timestamp() + desfase
    nuestro = plano(programa.title)
    i = bisect.bisect_left(inicios, momento - MARGEN)
    while i < len(inicios) and inicios[i] <= momento + MARGEN:
        d = suyos[i]
        if sin_titulo or parecido(nuestro, d['plano']):
            return d
        i += 1
    return None


def desfase_de(programas, suyos, inicios):
    """La hora entera que hay que sumar a la nuestra para dar con la suya."""
    mejor, aciertos = 0, -1
    for desfase in DESFASES:
        n = sum(1 for p in programas
                if not generico(p.title) and buscar(p, suyos, inicios, desfase, False))
        # En caso de empate, sin desfase.
        if n > aciertos * 1.5 or (aciertos <= 0 and n > 0):
            mejor, aciertos = desfase, n
    return mejor


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
    desfasados = {}
    for canal, suyos in fuente.items():
        programas = list(Program.objects.filter(
            channel=canal,
            start_time__gte=ahora - timedelta(hours=36),
            start_time__lte=ahora + timedelta(days=8),
        ))
        suyos.sort(key=lambda d: d['ini'])
        inicios = [d['ini'].timestamp() for d in suyos]
        desfase = desfase_de(programas, suyos, inicios)
        if desfase:
            desfasados[canal.name] = desfase // 3600
        cambiados = []
        for p in programas:
            sin_titulo = generico(p.title)
            # "Cine" a secas puede ganar el genero, asi que no se da por completo.
            sin_genero = plano(p.category) in ('cine', 'pelicula', 'peliculas', 'series', 'serie')
            if not sin_titulo and not sin_genero and \
                    all(getattr(p, campo) not in ('', None) for campo in CAMPOS):
                continue
            mejor = buscar(p, suyos, inicios, desfase, sin_titulo)
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
            if mas_completa(mejor['category'], p.category):
                p.category = mejor['category']
                cambio = True
            if cambio:
                cambiados.append(p)
        if cambiados and guardar:
            Program.objects.bulk_update(cambiados, ('title',) + CAMPOS, batch_size=500)
        tocados += len(cambiados)
    if desfasados:
        logger.warning('La guia de %s va con la hora cambiada en: %s', url, desfasados)
    logger.info('Guia completada con %s: %s programas en %s canales', url, tocados, len(fuente))
    return {'programas': tocados, 'canales': len(fuente), 'desfasados': desfasados}
