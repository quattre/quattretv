"""
El reparto de lo que se ve en el videoclub, con foto, para la ficha.

De donde sale, por lo que se puede usar en un servicio de pago:
- Series: TVmaze. Su API es CC BY-SA, "para cualquier uso" citando la fuente;
  trae el reparto con el personaje y la foto de cada actor.
- Peliculas: Wikidata (datos CC0) y las fotos de Wikimedia Commons. Cada foto
  tiene su licencia: solo se usan las que permiten uso comercial (CC0,
  dominio publico, CC BY, CC BY-SA) y se cita al autor. Las NC y ND, no.
  Carteles de pelicula ahi no hay; solo fotos de los actores.
TMDB tendria mas, pero su uso comercial pide un acuerdo de pago.

Como las caratulas: solo con el titulo exacto (y el año si lo hay), porque un
reparto equivocado es peor que ninguno. Lo encontrado se guarda un mes y lo no
encontrado una semana. Si una fuente tarda o falla, la ficha sale sin reparto.
"""
import hashlib
import logging
import re

import requests
from django.core.cache import cache

from .caratulas import limpiar
from .semana import plano

logger = logging.getLogger(__name__)

TVMAZE = 'https://api.tvmaze.com'
SPARQL = 'https://query.wikidata.org/sparql'
WIKIDATA = 'https://www.wikidata.org/w/api.php'
COMMONS = 'https://commons.wikimedia.org/w/api.php'
# Wikimedia pide identificarse; sin esto contesta 403.
CABECERAS = {'User-Agent': 'QuattreTV/1.0 (+https://iptv2.quattre.com) reparto-videoclub'}
ESPERA = 6
IDIOMAS_SERIE = ('English', 'Spanish', 'Catalan')
MAXIMO = 6
SI, NO = 30 * 86400, 7 * 86400
# Peliculas, telefilmes y animacion.
TIPOS_PELI = ('wd:Q11424', 'wd:Q506240', 'wd:Q24862', 'wd:Q202866', 'wd:Q29168811')
LICENCIA_OK = re.compile(r'^(cc0|public domain|pd\b|cc[ -]by(-sa)?[ -]\d)', re.I)
LICENCIA_NO = re.compile(r'\b(nc|nd)\b', re.I)


def _clave(titulo, anio, tipo):
    return 'reparto:' + hashlib.md5(('%s|%s|%s' % (plano(titulo), anio or '', tipo)).encode()).hexdigest()


def buscar(titulo, anio='', tipo='movie'):
    """{'personas': [{nombre, papel, foto, autor, licencia}], 'fuente': ...} o vacio."""
    consulta = limpiar(titulo or '')
    if len(consulta) < 2:
        return {}
    clave = _clave(consulta, anio, tipo)
    try:
        guardado = cache.get(clave)
    except Exception:
        guardado = None
    if guardado is not None:
        return guardado
    try:
        if tipo == 'tv':
            res = de_tvmaze(consulta, anio)
        else:
            res = de_wikidata(consulta, anio)
    except (requests.RequestException, ValueError, KeyError) as error:
        # Fallo de la fuente: no se guarda, se probara la proxima vez.
        logger.warning('reparto de %s: %s', consulta, error)
        return {}
    try:
        cache.set(clave, res, SI if res.get('personas') else NO)
    except Exception:
        pass
    return res


def de_tvmaze(titulo, anio=''):
    r = requests.get(TVMAZE + '/search/shows', params={'q': titulo}, timeout=ESPERA)
    r.raise_for_status()
    buscado = plano(titulo)
    for resultado in r.json()[:5]:
        serie = resultado.get('show') or {}
        if plano(serie.get('name')) != buscado:
            continue
        # Lo que se emite aqui es casi siempre de habla inglesa o española:
        # "Big Bang" daba un programa noruego con el mismo nombre.
        if serie.get('language') not in IDIOMAS_SERIE:
            continue
        if anio and (serie.get('premiered') or '')[:4] not in ('', str(anio)):
            continue
        c = requests.get('%s/shows/%s/cast' % (TVMAZE, serie['id']), timeout=ESPERA)
        c.raise_for_status()
        personas = []
        for papel in c.json():
            p = papel.get('person') or {}
            foto = (p.get('image') or {}).get('medium') or ''
            if not p.get('name'):
                continue
            personas.append({'nombre': p['name'], 'papel': (papel.get('character') or {}).get('name', ''),
                             'foto': foto, 'autor': '', 'licencia': ''})
            if len(personas) >= MAXIMO:
                break
        return {'personas': personas, 'fuente': 'TVmaze (tvmaze.com, CC BY-SA)'}
    return {}


def _sparql(consulta):
    r = requests.get(SPARQL, params={'query': consulta, 'format': 'json'}, headers=CABECERAS, timeout=ESPERA)
    r.raise_for_status()
    return r.json()['results']['bindings']


def de_wikidata(titulo, anio=''):
    """La pelicula por su titulo exacto en español (o en ingles) y su año."""
    texto = titulo.replace('\\', '').replace('"', '')
    filtro = 'FILTER(YEAR(?fecha) = %d)' % int(anio) if str(anio).isdigit() else ''
    filas = _sparql("""
        SELECT DISTINCT ?peli WHERE {
          VALUES ?tipo { %s }
          # El titulo de España suele ser un alias: el nombre principal en
          # español es a veces el de Hispanoamerica ("Arma mortal").
          { ?peli rdfs:label "%s"@es } UNION { ?peli skos:altLabel "%s"@es } UNION { ?peli rdfs:label "%s"@en }
          ?peli wdt:P31 ?tipo .
          OPTIONAL { ?peli wdt:P577 ?fecha }
          %s
        } LIMIT 3""" % (' '.join(TIPOS_PELI), texto, texto, texto, filtro))
    pelis = [f['peli']['value'].rsplit('/', 1)[-1] for f in filas]
    # Dos peliculas con el mismo titulo y sin año para distinguirlas: mejor nada.
    if len(pelis) != 1:
        return {}
    qid = pelis[0]
    e = requests.get(WIKIDATA, params={'action': 'wbgetentities', 'ids': qid, 'props': 'claims',
                                       'format': 'json'}, headers=CABECERAS, timeout=ESPERA)
    e.raise_for_status()
    reparto = e.json()['entities'][qid].get('claims', {}).get('P161', [])
    actores, papeles = [], {}
    for d in reparto:
        v = ((d.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {}
        if not v.get('id') or v['id'] in actores:
            continue
        actores.append(v['id'])
        for q in (d.get('qualifiers') or {}).get('P453', []):
            pv = (q.get('datavalue') or {}).get('value') or {}
            if pv.get('id'):
                papeles[v['id']] = pv['id']
        if len(actores) >= MAXIMO:
            break
    if not actores:
        return {}
    ids = actores + list(papeles.values())
    g = requests.get(WIKIDATA, params={'action': 'wbgetentities', 'ids': '|'.join(ids),
                                       'props': 'labels|claims', 'languages': 'es|en',
                                       'format': 'json'}, headers=CABECERAS, timeout=ESPERA)
    g.raise_for_status()
    ent = g.json()['entities']

    def nombre(i):
        labels = (ent.get(i) or {}).get('labels', {})
        return (labels.get('es') or labels.get('en') or {}).get('value', '')

    fichero = {}
    for a in actores:
        for d in (ent.get(a) or {}).get('claims', {}).get('P18', [])[:1]:
            f = ((d.get('mainsnak') or {}).get('datavalue') or {}).get('value')
            if f:
                fichero[a] = 'File:' + f
    fotos = fotos_commons(list(fichero.values()))
    personas = []
    for a in actores:
        if not nombre(a):
            continue
        foto = fotos.get(fichero.get(a), {})
        personas.append({'nombre': nombre(a), 'papel': nombre(papeles[a]) if a in papeles else '',
                         'foto': foto.get('url', ''), 'autor': foto.get('autor', ''),
                         'licencia': foto.get('licencia', '')})
    return {'personas': personas, 'fuente': 'Wikidata; fotos de Wikimedia Commons'}


def fotos_commons(ficheros):
    """{'File:x.jpg': {url, autor, licencia}} solo de las que permiten uso comercial."""
    if not ficheros:
        return {}
    r = requests.get(COMMONS, params={'action': 'query', 'titles': '|'.join(ficheros[:50]),
                                      'prop': 'imageinfo', 'iiprop': 'url|extmetadata',
                                      'iiurlwidth': 160, 'format': 'json'},
                     headers=CABECERAS, timeout=ESPERA)
    r.raise_for_status()
    q = r.json().get('query', {})
    # Commons normaliza los nombres (espacios, mayusculas): se deshace.
    normal = {n['to']: n['from'] for n in q.get('normalized', [])}
    res = {}
    for pagina in q.get('pages', {}).values():
        info = (pagina.get('imageinfo') or [{}])[0]
        meta = info.get('extmetadata') or {}
        licencia = (meta.get('LicenseShortName') or {}).get('value', '')
        if not LICENCIA_OK.search(licencia) or LICENCIA_NO.search(licencia):
            continue
        autor = re.sub(r'<[^>]+>', '', (meta.get('Artist') or {}).get('value', '')).strip()
        titulo = pagina.get('title', '')
        res[normal.get(titulo, titulo)] = {'url': info.get('thumburl') or info.get('url', ''),
                                           'autor': autor[:80], 'licencia': licencia}
    return res
