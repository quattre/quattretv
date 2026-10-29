"""
Caratulas para lo que la guia no trae.

Las guias traen imagen en el 71 % de los programas (y mas desde que se
completan con dobleM, ver apps/epg/completar.py). Para lo que sigue sin ella:

- Las fuentes se eligen en el panel (Configuracion > Caratulas, modelo
  FuenteCaratula): se prueban por orden y, si una falla o no la tiene, se pasa
  a la siguiente.
- TVmaze, gratis y sin clave, para series e infantiles. Solo pide que se le
  cite, y se hace en la pagina del panel.
- TMDB, con clave, para todo y sobre todo para las peliculas; busca en
  español, asi que encuentra "Phineas y Ferb". Su uso comercial pide su
  licencia comercial.
- OMDb (con clave), de reserva.

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


# Lo que sabe buscar cada fuente, y si necesita clave.
SABE = {'tmdb': ('movie', 'tv'), 'tvmaze': ('tv',), 'omdb': ('movie', 'tv')}
CON_CLAVE = ('tmdb', 'omdb')


def fuentes():
    """Las fuentes activas, por orden, que se pueden usar (las de clave, con clave)."""
    from apps.epg.models import FuenteCaratula
    try:
        lista = list(FuenteCaratula.objects.filter(activa=True))
    except Exception:
        lista = []
    utiles = []
    for f in lista:
        if f.tipo == 'tmdb' and not f.clave:
            f.clave = settings.QUATTRETV.get('TMDB_API_KEY', '')
        if f.tipo in CON_CLAVE and not f.clave:
            continue
        utiles.append(f)
    return utiles


def proveedores():
    return [f.tipo for f in fuentes()]


def _hash(titulo):
    return hashlib.md5(plano(titulo).encode()).hexdigest()


def clave_de(grupo, titulo):
    """Donde se guarda la caratula encontrada. No depende de las fuentes: cambiarlas no la pierde."""
    return 'caratula:v3:%s:%s' % (GRUPOS.get(grupo, ''), _hash(titulo))


def clave_no(grupo, titulo, provs):
    # Lo que no se encontro, con las fuentes en la clave: el dia que se añade
    # o se reordena una, se vuelve a buscar.
    return 'caratula:v3:no:%s:%s:%s' % ('+'.join(provs), GRUPOS.get(grupo, ''), _hash(titulo))


def _clave_vieja(grupo, titulo):
    # Las encontradas antes de poder elegir fuentes (solo habia TVmaze).
    return 'caratula:v2:tvmaze:%s:%s' % (GRUPOS.get(grupo, ''), _hash(titulo))


def completar(items):
    """Pone la caratula guardada a las tarjetas que no traen imagen."""
    # Una lista por titulo: los capitulos de una serie se llaman igual, y con
    # un diccionario de uno solo la caratula le llegaba solo al ultimo (Bluey
    # salia sin imagen en 158 de sus emisiones).
    faltan = {}
    for i in items:
        if not i.get('img') and i.get('grupo') in GRUPOS:
            faltan.setdefault(clave_de(i['grupo'], i['titulo']), []).append(i)
    if not faltan:
        return
    guardadas = _leer(list(faltan))
    viejas = {_clave_vieja(l[0]['grupo'], l[0]['titulo']): c for c, l in faltan.items() if not guardadas.get(c)}
    for vieja, url in _leer(list(viejas)).items():
        if url:
            guardadas[viejas[vieja]] = url
    for clave, url in guardadas.items():
        if url:
            for i in faltan[clave]:
                i['img'] = url


def _leer(claves):
    """cache.get_many a trozos: pedir miles de claves de una vez falla sin decir nada."""
    guardadas = {}
    for n in range(0, len(claves), 200):
        try:
            guardadas.update(cache.get_many(claves[n:n + 200]))
        except Exception:
            break
    return guardadas


def limpiar(titulo):
    """'Castle (T3)' -> 'Castle'. Lo que la guia añade y TMDB no conoce."""
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', titulo)
    t = re.sub(r'\s+(T|Temp\.?|Temporada)\s*\d+.*$', '', t, flags=re.I)
    t = re.sub(r'\s*[:\-]\s*(cap[ií]tulo|episodio)\b.*$', '', t, flags=re.I)
    return t.strip()


def _pedir(ruta, parametros, clave):
    cabeceras = {}
    # Vale la clave corta (v3) y el token de lectura (v4), que es mucho mas largo.
    if len(clave) > 40:
        cabeceras['Authorization'] = 'Bearer ' + clave
    else:
        parametros = dict(parametros, api_key=clave)
    r = requests.get(API + ruta, params=parametros, headers=cabeceras, timeout=10)
    r.raise_for_status()
    return r.json()


def buscar_tvmaze(titulo, anio='', tipo='tv', clave=''):
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


def buscar(titulo, anio, tipo, lista=None):
    """
    La caratula de la primera fuente que la tenga, o '' si ninguna tiene una
    que encaje seguro. Si una fuente falla (caida, clave mala, limite), se
    apunta el error en el panel y se sigue con la siguiente.
    """
    from django.utils import timezone
    for f in (lista if lista is not None else fuentes()):
        if tipo not in SABE.get(f.tipo, ()):
            continue
        f.buscadas += 1
        f.ultimo_uso = timezone.now()
        try:
            url = BUSCADORES[f.tipo](titulo, anio, tipo, f.clave)
            if f.tipo == 'tvmaze':
                # TVmaze pide no pasar de unas 20 peticiones cada pocos segundos.
                time.sleep(1)
        except (requests.RequestException, ValueError) as error:
            f.ultimo_error = ('%s: %s' % (timezone.localtime().strftime('%d/%m %H:%M'), error))[:300]
            f.save(update_fields=['buscadas', 'ultimo_uso', 'ultimo_error'])
            continue
        if url:
            f.encontradas += 1
            f.save(update_fields=['buscadas', 'encontradas', 'ultimo_uso'])
            return url
        f.save(update_fields=['buscadas', 'ultimo_uso'])
    return ''


def buscar_omdb(titulo, anio, tipo, clave=''):
    """El cartel de OMDb (titulos en ingles, sobre todo), o ''."""
    consulta = limpiar(titulo)
    if len(consulta) < 2 or not clave:
        return ''
    parametros = {'apikey': clave, 't': consulta, 'type': 'movie' if tipo == 'movie' else 'series'}
    if anio and tipo == 'movie':
        parametros['y'] = anio
    r = requests.get('https://www.omdbapi.com/', params=parametros, timeout=10)
    r.raise_for_status()
    datos = r.json()
    if datos.get('Response') != 'True' or plano(datos.get('Title')) != plano(consulta):
        return ''
    cartel = datos.get('Poster') or ''
    return cartel if cartel.startswith('http') else ''


def buscar_tmdb(titulo, anio, tipo, clave=''):
    """La URL de la imagen en TMDB, o '' si no hay una que encaje seguro."""
    consulta = limpiar(titulo)
    if len(consulta) < 2:
        return ''
    parametros = {'query': consulta, 'language': 'es-ES', 'include_adult': 'false'}
    if anio and tipo == 'movie':
        parametros['year'] = anio
    datos = _pedir('/search/%s' % tipo, parametros, clave or settings.QUATTRETV.get('TMDB_API_KEY', ''))
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

    lista = fuentes()
    provs = [f.tipo for f in lista]
    tipos = {t for f in lista for t in SABE.get(f.tipo, ())}
    pendientes = {}
    for e in todas_las_emisiones():
        if e['img'] or e['grupo'] not in GRUPOS or GRUPOS[e['grupo']] not in tipos:
            continue
        pendientes.setdefault(clave_de(e['grupo'], e['titulo']), e)
    # Ya encontradas (ahora o antes de poder elegir fuentes) o ya buscadas sin
    # suerte con estas mismas fuentes.
    ya = _leer(list(pendientes))
    viejas = {_clave_vieja(e['grupo'], e['titulo']): c for c, e in pendientes.items() if c not in ya}
    for vieja, url in _leer(list(viejas)).items():
        if url:
            cache.set(viejas[vieja], url, SI_DIAS * 86400)
            ya[viejas[vieja]] = url
    nos = {clave_no(e['grupo'], e['titulo'], provs): c for c, e in pendientes.items() if c not in ya}
    for no in _leer(list(nos)):
        ya[nos[no]] = ''

    hechas = 0
    for clave, e in pendientes.items():
        if clave in ya or hechas >= maximo:
            continue
        url = buscar(e['titulo'], e['anio'], GRUPOS[e['grupo']], lista)
        if url:
            cache.set(clave, url, SI_DIAS * 86400)
        else:
            cache.set(clave_no(e['grupo'], e['titulo'], provs), 1, NO_DIAS * 86400)
        hechas += 1
    logger.info('Caratulas buscadas (%s): %s', '+'.join(provs), hechas)
    return hechas


BUSCADORES = {'tmdb': buscar_tmdb, 'tvmaze': buscar_tvmaze, 'omdb': buscar_omdb}
