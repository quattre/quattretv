"""
Caratulas para lo que la guia no trae.

Las guias traen imagen en el 71 % de los programas (y mas desde que se
completan con dobleM, ver apps/epg/completar.py). Para lo que sigue sin ella:

- TVmaze, gratis y sin clave, para series e infantiles. Solo pide que se le
  cite, y se hace en la pagina del panel.
- TMDB, si hay TMDB_API_KEY, para todo y sobre todo para las peliculas. Su
  uso comercial pide su licencia comercial.

La busqueda la hace una tarea periodica y no la peticion del deco: TMDB tarda
y el catalogo tiene que salir al momento. Lo encontrado se guarda en la cache
un mes; lo que no se encuentra, una semana, para no preguntarlo cada media
hora.

Solo se busca con coincidencia exacta del titulo (y del año, si la guia lo
trae): una caratula equivocada es peor que ninguna. Sin TMDB_API_KEY no se
hace nada y el catalogo sale con las imagenes de la guia.
"""
import hashlib
import logging
import re
import time

import requests
from django.conf import settings
from django.core.cache import cache

from .semana import plano

logger = logging.getLogger(__name__)

API = 'https://api.themoviedb.org/3'
TVMAZE = 'https://api.tvmaze.com'
IMAGENES = 'https://image.tmdb.org/t/p/w780'
SI_DIAS, NO_DIAS = 30, 7
# Las noticias y el deporte son de un dia: no estan en TMDB.
GRUPOS = {'peliculas': 'movie', 'series': 'tv', 'infantil': 'tv',
          'documentales': 'tv', 'entretenimiento': 'tv'}


def proveedores():
    return (['tmdb'] if settings.QUATTRETV.get('TMDB_API_KEY') else []) + ['tvmaze']


def clave_de(grupo, titulo):
    # Con los proveedores en la clave, lo que no encontro uno se vuelve a
    # buscar el dia que se añade otro.
    return 'caratula:v2:%s:%s:%s' % ('+'.join(proveedores()), GRUPOS.get(grupo, ''),
                                     hashlib.md5(plano(titulo).encode()).hexdigest())


def completar(items):
    """Pone la caratula guardada a las tarjetas que no traen imagen."""
    faltan = {clave_de(i['grupo'], i['titulo']): i for i in items
              if not i.get('img') and i.get('grupo') in GRUPOS}
    if not faltan:
        return
    try:
        guardadas = cache.get_many(list(faltan))
    except Exception:
        return
    for clave, url in guardadas.items():
        if url:
            faltan[clave]['img'] = url


def limpiar(titulo):
    """'Castle (T3)' -> 'Castle'. Lo que la guia añade y TMDB no conoce."""
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', titulo)
    t = re.sub(r'\s+(T|Temp\.?|Temporada)\s*\d+.*$', '', t, flags=re.I)
    t = re.sub(r'\s*[:\-]\s*(cap[ií]tulo|episodio)\b.*$', '', t, flags=re.I)
    return t.strip()


def _pedir(ruta, parametros):
    clave = settings.QUATTRETV.get('TMDB_API_KEY', '')
    cabeceras = {}
    # Vale la clave corta (v3) y el token de lectura (v4), que es mucho mas largo.
    if len(clave) > 40:
        cabeceras['Authorization'] = 'Bearer ' + clave
    else:
        parametros = dict(parametros, api_key=clave)
    r = requests.get(API + ruta, params=parametros, headers=cabeceras, timeout=10)
    r.raise_for_status()
    return r.json()


def buscar_tvmaze(titulo):
    """
    El cartel de la serie en TVmaze, o ''. El pequeño (210x295, unos 20 KB):
    las imagenes horizontales que tiene son de 1920x1080 y 350 KB, y diez de
    esas en pantalla son demasiado para un MAG.
    """
    consulta = limpiar(titulo)
    if len(consulta) < 2:
        return ''
    r = requests.get(TVMAZE + '/search/shows', params={'q': consulta}, timeout=10)
    r.raise_for_status()
    buscado = plano(consulta)
    for resultado in r.json()[:5]:
        serie = resultado.get('show') or {}
        if plano(serie.get('name')) == buscado:
            cartel = serie.get('image') or {}
            return cartel.get('medium') or cartel.get('original') or ''
    return ''


def buscar(titulo, anio, tipo):
    """La caratula de quien la tenga, o '' si nadie tiene una que encaje seguro."""
    if 'tmdb' in proveedores():
        url = buscar_tmdb(titulo, anio, tipo)
        if url:
            return url
    if tipo == 'tv':
        # TVmaze pide no pasar de 20 peticiones cada 10 segundos.
        time.sleep(1)
        return buscar_tvmaze(titulo)
    return ''


def buscar_tmdb(titulo, anio, tipo):
    """La URL de la imagen en TMDB, o '' si no hay una que encaje seguro."""
    consulta = limpiar(titulo)
    if len(consulta) < 2:
        return ''
    parametros = {'query': consulta, 'language': 'es-ES', 'include_adult': 'false'}
    if anio and tipo == 'movie':
        parametros['year'] = anio
    datos = _pedir('/search/%s' % tipo, parametros)
    buscado = plano(consulta)
    for r in datos.get('results', [])[:10]:
        nombres = (r.get('title'), r.get('original_title'), r.get('name'), r.get('original_name'))
        if buscado not in [plano(n) for n in nombres if n]:
            continue
        fecha = r.get('release_date') or r.get('first_air_date') or ''
        if anio and tipo == 'movie' and fecha[:4].isdigit() and abs(int(fecha[:4]) - int(anio)) > 1:
            continue
        # Horizontal, como las de la guia; si no hay, el cartel.
        ruta = r.get('backdrop_path') or r.get('poster_path')
        if ruta:
            return IMAGENES + ruta
    return ''


def buscar_las_que_faltan(maximo=200):
    """Busca las caratulas que faltan en lo que hay en el archivo."""
    from .semana import todas_las_emisiones

    pendientes = {}
    for e in todas_las_emisiones():
        if e['img'] or e['grupo'] not in GRUPOS:
            continue
        # Sin TMDB solo hay donde buscar series.
        if GRUPOS[e['grupo']] == 'movie' and 'tmdb' not in proveedores():
            continue
        pendientes.setdefault(clave_de(e['grupo'], e['titulo']), e)
    try:
        ya = cache.get_many(list(pendientes))
    except Exception:
        return 0

    hechas = 0
    for clave, e in pendientes.items():
        if clave in ya or hechas >= maximo:
            continue
        try:
            url = buscar(e['titulo'], e['anio'], GRUPOS[e['grupo']])
        except (requests.RequestException, ValueError) as error:
            logger.warning('No se pudo buscar la caratula de %s: %s', e['titulo'], error)
            break
        cache.set(clave, url, (SI_DIAS if url else NO_DIAS) * 86400)
        hechas += 1
    logger.info('Caratulas buscadas (%s): %s', '+'.join(proveedores()), hechas)
    return hechas
