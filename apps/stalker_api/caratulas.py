"""
Caratulas para lo que la guia no trae, buscadas en TMDB.

Las guias traen imagen en el 71 % de los programas, pero en las peliculas,
que es donde mas se nota, solo en un tercio. TMDB tiene casi todas.

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

import requests
from django.conf import settings
from django.core.cache import cache

from .semana import plano

logger = logging.getLogger(__name__)

API = 'https://api.themoviedb.org/3'
IMAGENES = 'https://image.tmdb.org/t/p/w780'
SI_DIAS, NO_DIAS = 30, 7
# Las noticias y el deporte son de un dia: no estan en TMDB.
GRUPOS = {'peliculas': 'movie', 'series': 'tv', 'infantil': 'tv',
          'documentales': 'tv', 'entretenimiento': 'tv'}


def clave_de(grupo, titulo):
    return 'caratula:v1:%s:%s' % (GRUPOS.get(grupo, ''),
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


def buscar(titulo, anio, tipo):
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
    """Busca en TMDB las caratulas que faltan en lo que hay en el archivo."""
    from .semana import todas_las_emisiones

    if not settings.QUATTRETV.get('TMDB_API_KEY'):
        return 0
    pendientes = {}
    for e in todas_las_emisiones():
        if e['img'] or e['grupo'] not in GRUPOS:
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
        except requests.RequestException as error:
            logger.warning('TMDB no contesta: %s', error)
            break
        cache.set(clave, url, (SI_DIAS if url else NO_DIAS) * 86400)
        hechas += 1
    logger.info('Caratulas buscadas en TMDB: %s', hechas)
    return hechas
