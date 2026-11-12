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
WIKIPEDIA = 'https://es.wikipedia.org/w/api.php'
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


def guardado(titulo, anio='', tipo='movie'):
    """Lo ya buscado, o None si no se ha buscado todavia."""
    consulta = limpiar(titulo or '')
    if len(consulta) < 2:
        return {}
    try:
        return cache.get(_clave(consulta, anio, tipo))
    except Exception:
        return {}


def pedir(titulo, anio='', tipo='movie'):
    """
    Lo guardado o, si no lo hay, la busqueda encargada a Celery y None. La
    primera busqueda tarda hasta unos segundos (Wikidata) y no puede ocupar un
    proceso del servidor mientras tanto: los decos se quedarian esperando.
    """
    ya = guardado(titulo, anio, tipo)
    if ya is not None:
        return ya
    from apps.epg.tasks import buscar_reparto
    try:
        if cache.add('reparto:buscando:' + _clave(limpiar(titulo), anio, tipo), 1, 60):
            buscar_reparto.delay(titulo, anio, tipo)
    except Exception:
        return {}
    return None


def buscar_los_que_faltan(minutos=20):
    """
    Busca de antemano el reparto de lo que hay en el videoclub y de las pelis
    y series de la guia de hoy y mañana, para que la ficha lo tenga al abrirla
    (como las caratulas). Uno detras de otro y con tiempo tope: Wikidata pide
    no apretarle, y la tarea no puede quedarse con Celery para ella sola.
    """
    import time
    from datetime import timedelta
    from django.utils import timezone
    from apps.epg.models import Program
    from .caratulas import GRUPOS
    from .semana import todas_las_emisiones

    if not cache.add('reparto:precarga', 1, minutos * 60 + 60):
        return 0
    pendientes = {}

    def apuntar(titulo, anio, tipo):
        anio = str(anio or '')
        anio = anio if anio.isdigit() else ''
        clave = _clave(limpiar(titulo or ''), anio, tipo)
        if clave not in pendientes:
            pendientes[clave] = (titulo, anio, tipo)

    # Lo del videoclub, como lo pide su ficha (ver handle_archive_cast).
    for e in todas_las_emisiones():
        if e['grupo'] in ('peliculas', 'series', 'infantil', 'documentales'):
            apuntar(e['titulo'], e['anio'], GRUPOS[e['grupo']])
    # Y lo de la guia, como lo pide la suya (repartoEnFicha en el portal).
    ahora = timezone.now()
    for titulo, anio, cat in Program.objects.filter(
            start_time__lt=ahora + timedelta(hours=36), end_time__gt=ahora) \
            .exclude(category='').values_list('title', 'year', 'category').distinct():
        cat = (cat or '').lower()
        if re.match(r'(cine|pel)', cat):
            apuntar(titulo, anio, 'movie')
        elif cat.startswith('serie'):
            apuntar(titulo, anio, 'tv')

    tope = time.time() + minutos * 60
    hechas = 0
    try:
        for clave, (titulo, anio, tipo) in pendientes.items():
            if time.time() > tope:
                break
            if guardado(titulo, anio, tipo) is not None:
                continue
            buscar(titulo, anio, tipo)
            hechas += 1
    finally:
        cache.delete('reparto:precarga')
    logger.info('Reparto buscado de antemano: %s de %s titulos', hechas, len(pendientes))
    return hechas


def buscar(titulo, anio='', tipo='movie'):
    """{'personas': [{nombre, papel, foto, autor, licencia}], 'fuente': ...} o vacio."""
    consulta = limpiar(titulo or '')
    if len(consulta) < 2:
        return {}
    clave = _clave(consulta, anio, tipo)
    ya = guardado(titulo, anio, tipo)
    if ya is not None:
        return ya
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
        return reparto_tvmaze(serie['id'])
    # En TVmaze van por el nombre original ("The Golden Girls") y la guia da
    # el de aqui ("Las chicas de oro"): la Wikipedia en español lo encuentra y
    # Wikidata guarda el numero de la serie en TVmaze (P8600).
    ids = por_wikipedia(titulo, None, serie=True)
    if len(ids) == 1:
        return reparto_tvmaze(ids[0])
    return {}


def reparto_tvmaze(id_serie):
    c = requests.get('%s/shows/%s/cast' % (TVMAZE, id_serie), timeout=ESPERA)
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
    return {'personas': personas, 'fuente': 'TVmaze (tvmaze.com, CC BY-SA)'} if personas else {}


def _sparql(consulta):
    r = requests.get(SPARQL, params={'query': consulta, 'format': 'json'}, headers=CABECERAS, timeout=ESPERA + 4)
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
    if not pelis and str(anio).isdigit():
        pelis = por_wikipedia(titulo, int(anio))
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


def por_wikipedia(titulo, anio, serie=False):
    """
    La pelicula por la Wikipedia en español, que tiene los titulos de España
    como redirecciones ("Arma letal" -> Lethal Weapon) aunque Wikidata no los
    tenga. Solo se acepta si en Wikidata es una pelicula de ese año. Con
    serie=True, las series con numero de TVmaze (y se devuelve ese numero).
    """
    busqueda = ('"%s" serie de televisión' % titulo) if serie else ('"%s" película %d' % (titulo, anio))
    r = requests.get(WIKIPEDIA, params={'action': 'query', 'list': 'search', 'srlimit': 3,
                                        'srsearch': busqueda, 'format': 'json'},
                     headers=CABECERAS, timeout=ESPERA)
    r.raise_for_status()
    titulos = [x['title'] for x in r.json().get('query', {}).get('search', [])]
    if not titulos:
        return []
    p = requests.get(WIKIPEDIA, params={'action': 'query', 'titles': '|'.join(titulos), 'redirects': 1,
                                        'prop': 'pageprops', 'ppprop': 'wikibase_item', 'format': 'json'},
                     headers=CABECERAS, timeout=ESPERA)
    p.raise_for_status()
    qids = [pg['pageprops']['wikibase_item'] for pg in p.json().get('query', {}).get('pages', {}).values()
            if (pg.get('pageprops') or {}).get('wikibase_item')]
    if not qids:
        return []
    e = requests.get(WIKIDATA, params={'action': 'wbgetentities', 'ids': '|'.join(qids), 'props': 'claims',
                                       'format': 'json'}, headers=CABECERAS, timeout=ESPERA)
    e.raise_for_status()
    tipos = {t.split(':')[1] for t in TIPOS_PELI}
    buenas = []
    for qid, ent in e.json().get('entities', {}).items():
        claims = ent.get('claims', {})
        if serie:
            tvmaze = [((c.get('mainsnak') or {}).get('datavalue') or {}).get('value')
                      for c in claims.get('P8600', [])]
            buenas += [t for t in tvmaze if t and t not in buenas]
            continue
        es_peli = any(((c.get('mainsnak') or {}).get('datavalue') or {}).get('value', {}).get('id') in tipos
                      for c in claims.get('P31', []))
        anios = {(((c.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {}).get('time', '')[1:5]
                 for c in claims.get('P577', [])}
        if es_peli and str(anio) in anios:
            buenas.append(qid)
    return buenas


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
        # Los parentesis y comillas de algunos nombres rompen el url() del CSS.
        url = (info.get('thumburl') or info.get('url', '')).replace('(', '%28').replace(')', '%29') \
            .replace("'", '%27').replace(' ', '%20')
        res[normal.get(titulo, titulo)] = {'url': url,
                                           'autor': autor[:80], 'licencia': licencia}
    return res
