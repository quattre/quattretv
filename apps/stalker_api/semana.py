"""
"Ultimos 7 dias": lo emitido que esta en el archivo, ordenado por programa.

Es el mismo archivo de siempre (el catchup de cada canal), solo que en vez de
buscarlo canal a canal y hora a hora en la guia, se presenta como un catalogo
con caratulas: peliculas, series, deportes... Se arma con la guia de los
canales que tienen archivo para este aparato, asi que se renueva solo a medida
que el archivo avanza y lo viejo se borra.

Las guias casi nunca dicen de que tipo es un programa (de 9.413 de una semana,
117 lo decian), asi que el tipo se deduce: la categoria de la guia si la hay,
si no unas palabras del titulo, y si no el tipo de canal.
"""
import hashlib
import re
import unicodedata
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

GRUPOS = [
    ('peliculas', 'Peliculas'),
    ('series', 'Series'),
    ('deportes', 'Deportes'),
    ('infantil', 'Infantil'),
    ('documentales', 'Documentales'),
    ('entretenimiento', 'Entretenimiento'),
    ('noticias', 'Noticias'),
]

# Antes cada fila se cortaba en 40 y no salian todos los titulos. De verdad
# son mas de 1.500 (solo peliculas, unas 600) y 1,2 MB, que un MAG no traga de
# una vez: cada fila llega con las primeras PAGINA y el resto se pide al
# avanzar por ella.
POR_GRUPO = None
PAGINA = 30
# Minutos. Lo mas corto son el tiempo, avances y cortinillas; los dibujos si
# duran poco de verdad.
DURACION_MINIMA = 15
DURACION_MINIMA_INFANTIL = 7
CACHE_SEGUNDOS = 300

# Generos de ficcion: segun lo que dure es una pelicula o un capitulo.
FICCION = ('drama', 'comedia', 'comedy', 'suspense', 'thriller', 'accion',
           'action', 'terror', 'horror', 'western', 'romance', 'romant',
           'aventura', 'adventure', 'ciencia ficcion', 'sci-fi', 'fantas',
           'policiac', 'crimen', 'crime', 'belic', 'misterio')

# Por categoria de la guia, en este orden.
PALABRAS = [
    ('peliculas', ('cine', 'film', 'pelicula', 'movie')),
    ('series', ('serie',)),
    ('deportes', ('deporte', 'sport')),
    ('infantil', ('infantil', 'kids', 'children', 'animacion', 'dibujos')),
    ('noticias', ('news', 'informa', 'noticia')),
    ('documentales', ('document', 'naturaleza', 'nature', 'cultur', 'historia',
                      'ciencia', 'viaje')),
    ('entretenimiento', ('entreten', 'entertain', 'programa', 'music', 'musica',
                         'concurso', 'magazine', 'reality', 'humor', 'cocina',
                         'estilo', 'lifestyle', 'ocio', 'otros')),
]

# Por titulo, cuando la guia no dice nada.
TITULOS = [
    ('noticias', ('telediario', 'noticias', 'informativo', 'diario de la',
                  'telenoticies', 'news')),
    ('deportes', ('futbol', 'laliga', 'la liga', 'champions', 'motogp',
                  'formula 1', 'baloncesto', 'tenis', 'ciclismo', 'estadio')),
]

# Filas de peliculas por genero, debajo de la de todas. La guia de dobleM lo
# trae como "Cine,Terror,Suspense" y una pelicula puede estar en varias.
GENEROS = [
    ('cine-terror', 'Peliculas de terror', ('terror', 'horror')),
    ('cine-accion', 'Accion y aventuras', ('accion', 'action', 'aventura', 'adventure', 'belic')),
    ('cine-comedia', 'Comedias', ('comedia', 'comedy')),
    ('cine-suspense', 'Suspense y policiacas', ('thriller', 'suspense', 'policiac', 'crimen',
                                                'crime', 'intriga', 'misterio')),
    ('cine-drama', 'Dramas', ('drama',)),
    ('cine-romantico', 'Romanticas', ('romant', 'romance')),
    ('cine-ficcion', 'Ciencia ficcion y fantasia', ('ciencia ficcion', 'sci-fi', 'fantas')),
    ('cine-familiar', 'Animacion y familiares', ('animacion', 'familiar', 'infantil')),
    ('cine-oeste', 'Oeste', ('oeste', 'western')),
    ('cine-docu', 'Cine documental', ('document',)),
]
GENERO_MINIMO = 3       # con menos peliculas la fila no merece la pena
# Como el "Last chance" de Netflix: las que se borran en menos de dos dias.
ULTIMA = ('cine-ultima', 'Ultima oportunidad')
ULTIMA_HORAS = 24

# Lo que no es un programa que alguien quiera volver a ver.
FUERA = ('teletienda', 'televenta', 'tienda en casa', 'juwelo', 'cierre de emision', 'el tiempo',
         'fin de emision', 'programacion de cierre')

# Por el tipo de canal, como ultimo recurso.
CANALES = {
    'infantil': 'infantil',
    'deportes': 'deportes',
    'documentales': 'documentales',
    'entretenimiento': 'entretenimiento',
    'lifestyle': 'entretenimiento',
}


# Alguna fuente pone la temporada en el titulo: "Chicago Fire (T9)",
# "Estadio 2.0 (T2026)". Asi el mismo programa salia en dos tarjetas.
TEMPORADA = re.compile(r'\s*\(T\d+\)\s*$')


def sin_temporada(titulo):
    return TEMPORADA.sub('', titulo or '').strip()


def plano(texto):
    """Minusculas y sin acentos, para comparar."""
    texto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in texto if not unicodedata.combining(c)).lower().strip()


def grupo_de(titulo, categoria, minutos, anio, tipo_canal):
    """
    (grupo, seguro) de un programa, o (None, True) si no vale la pena
    ofrecerlo. "seguro" es que lo dice la guia o el canal es de cine y series;
    si no, es una suposicion que otra emision del mismo titulo puede corregir.
    """
    t, canal = plano(titulo), plano(tipo_canal)
    # dobleM pone el tipo y detras los generos: "Series,Drama", "Cine,Terror".
    # El tipo es lo primero; con todo, "Series,Drama" de 90 minutos salia
    # como pelicula.
    c = plano(categoria).split(',')[0].strip()
    if any(p in t for p in FUERA):
        return None, True
    if c == 'cine' and 'programa de cine' in plano(categoria):
        return 'entretenimiento', True
    largo = minutos >= 75

    if c:
        if any(p in c for p in FICCION):
            return ('peliculas' if largo else 'series'), True
        for grupo, palabras in PALABRAS:
            if any(p in c for p in palabras):
                return grupo, True

    for grupo, palabras in TITULOS:
        if any(p in t for p in palabras):
            return grupo, True

    if 'cine' in canal or 'serie' in canal:
        return ('peliculas' if largo else 'series'), True
    if canal in CANALES:
        return CANALES[canal], False
    # Aqui se miraba "largo y con año = pelicula", pero desde que las guias
    # traen el año de casi todo, Masterchef o El hormiguero salian como
    # peliculas. En una generalista sin categoria no se puede saber.
    return 'entretenimiento', False


def generos_de(categoria):
    """Las filas de genero de una pelicula: "Cine,Terror" -> ['cine-terror']."""
    resto = plano(categoria).split(',', 1)
    # "Cine,Terror" o "Peliculas de terror": el genero va detras del tipo.
    texto = resto[1] if len(resto) > 1 else resto[0]
    if texto.strip() in ('cine', 'pelicula', 'peliculas', 'film', 'movie', ''):
        return []
    return [g for g, _, palabras in GENEROS if any(p in texto for p in palabras)]


def canales_con_archivo(device):
    """{canal: horas de archivo} de lo que este aparato puede ver en diferido."""
    from apps.channels.models import Channel
    from .views import archivo_del_canal, canales_visibles, ventanas_de_archivo

    if device and device.user.tariff and not device.user.tariff.has_catchup:
        return {}
    canales = canales_visibles(
        Channel.objects.filter(is_active=True, has_catchup=True, is_adult=False)
        .select_related('category'), device)
    if device and device.user.tariff:
        from django.db.models import Q
        paquetes = device.user.tariff.channel_packages.values_list('id', flat=True)
        canales = canales.filter(
            Q(packages__id__in=paquetes) | Q(packages__isnull=True)).distinct()

    ventanas = ventanas_de_archivo()
    resultado = {}
    for canal in canales:
        tiene, horas = archivo_del_canal(canal, device, ventanas)
        if tiene:
            resultado[canal] = horas
    return resultado


# ---------- Correcciones del panel ----------

def version():
    """Cambia cada vez que se corrige algo en el panel: invalida la cache."""
    try:
        return cache.get('semana:version') or 0
    except Exception:
        return 0


def invalidar():
    try:
        cache.set('semana:version', int(timezone.now().timestamp() * 1000), None)
    except Exception:
        pass


def correcciones():
    """(filas ocultas, {clave del titulo: TituloSemana})."""
    from apps.epg.models import FilaSemana, TituloSemana
    clave = 'semana:correcciones:%s' % version()
    try:
        guardado = cache.get(clave)
        if guardado is not None:
            return guardado
    except Exception:
        pass
    ocultas = set(FilaSemana.objects.filter(visible=False).values_list('grupo', flat=True))
    titulos = {t.clave: t for t in TituloSemana.objects.all()}
    try:
        cache.set(clave, (ocultas, titulos), CACHE_SEGUNDOS)
    except Exception:
        pass
    return ocultas, titulos


def emisiones(canales, con_ocultos=False):
    """Lo ya emitido que sigue en el archivo de esos canales, lo mas nuevo antes."""
    from apps.epg.completar import generico
    from apps.epg.models import Program

    ahora = timezone.now()
    salida = []
    seguros = {}
    for canal, horas in canales.items():
        desde = ahora - timedelta(hours=horas)
        tipo_canal = canal.category.name if canal.category else ''
        programas = Program.objects.filter(
            channel=canal, start_time__gte=desde,
            end_time__lte=ahora - timedelta(minutes=2),
        ).only('title', 'description', 'start_time', 'end_time', 'category',
               'episode_title', 'year', 'icon')
        for p in programas:
            minutos = int((p.end_time - p.start_time).total_seconds() // 60)
            titulo = sin_temporada(p.title)
            # "Cine" o "Documental" a secas no dicen que es: mejor no ofrecerlo.
            if minutos < DURACION_MINIMA_INFANTIL or not titulo or generico(titulo):
                continue
            grupo, seguro = grupo_de(titulo, p.category, minutos, p.year, tipo_canal)
            if not grupo:
                continue
            if seguro:
                seguros.setdefault(plano(titulo), grupo)
            salida.append({
                'seguro': seguro,
                'grupo': grupo,
                'titulo': titulo,
                'sub': p.episode_title or '',
                'descr': (p.description or '')[:300],
                'generos': generos_de(p.category),
                'anio': p.year or '',
                'img': p.icon or '',
                'ch_id': str(canal.id),
                'canal': canal.name,
                'logo': canal.logo_display_url,
                'ini': int(p.start_time.timestamp()),
                'fin': int(p.end_time.timestamp()),
                # Cuando lo borra el grabador: lo que dura el archivo del canal.
                'caduca': int(p.start_time.timestamp()) + horas * 3600,
                'min': minutos,
            })

    # Big Bang en Neox salia como entretenimiento, porque la guia no lo dice y
    # Neox es un canal de entretenimiento; en Warner, que es de series, si se
    # sabe. Lo que se sabe de un titulo vale para todas sus emisiones.
    for e in salida:
        if not e.pop('seguro'):
            e['grupo'] = seguros.get(plano(e['titulo']), e['grupo'])

    # Lo que se ha corregido a mano en el panel manda sobre lo adivinado.
    _, corregidos = correcciones()
    if corregidos:
        quedan = []
        for e in salida:
            c = corregidos.get(plano(e['titulo']))
            if c:
                if c.oculto and not con_ocultos:
                    continue
                if c.grupo:
                    e['grupo'] = c.grupo
                if c.imagen:
                    e['img'] = c.imagen
            quedan.append(e)
        salida = quedan

    salida = [e for e in salida
              if e['min'] >= DURACION_MINIMA or e['grupo'] == 'infantil']
    salida.sort(key=lambda e: -e['ini'])
    return salida


def catalogo(device):
    """
    Las filas del catalogo. Cada tarjeta es un titulo: si se ha emitido varias
    veces (los capitulos de una serie, los telediarios) se juntan y la tarjeta
    lleva la emision mas reciente y cuantas hay.
    """
    canales = canales_con_archivo(device)
    if not canales:
        return []

    firma = ','.join(f'{c.id}:{h}' for c, h in sorted(canales.items(), key=lambda x: x[0].id))
    clave = 'semana:%s:%s' % (version(), hashlib.md5(firma.encode()).hexdigest())
    try:
        guardado = cache.get(clave)
        if guardado is not None:
            return guardado
    except Exception:
        pass

    ocultas, _ = correcciones()
    resultado = [f for f in filas_de(emisiones(canales))
                 if f['items'] and f['id'] not in ocultas
                 and not (f['id'].startswith('cine-') and 'peliculas' in ocultas)]
    try:
        cache.set(clave, resultado, CACHE_SEGUNDOS)
    except Exception:
        pass
    return resultado


def primeras(filas):
    """Las filas con sus primeras tarjetas y cuantas tiene cada una."""
    return [dict(f, items=f['items'][:PAGINA], total=len(f['items'])) for f in filas]


def mas_de_fila(device, fila, desde):
    for f in catalogo(device):
        if f['id'] == fila:
            return f['items'][desde:desde + PAGINA]
    return []


def filas_de(lista, por_grupo=POR_GRUPO):
    """
    Junta las emisiones en tarjetas, una por titulo, y las reparte en filas.

    Cada fila se llena por turnos de canal: lo ultimo de cada canal, luego lo
    penultimo de cada uno... Por orden de emision a secas, los canales de cine,
    que echan peliculas sin parar, llenaban la fila y las de La 1 o Antena 3 no
    salian nunca; con un tope fijo por canal, las filas de un solo canal
    (deportes, casi todo Teledeporte) se quedaban medio vacias.
    """
    from . import caratulas

    tarjetas = {g: {} for g, _ in GRUPOS}
    for e in lista:                              # lo mas nuevo primero
        de_fila = tarjetas[e['grupo']]
        clave_titulo = plano(e['titulo'])
        if clave_titulo in de_fila:
            de_fila[clave_titulo]['n'] += 1
            # Si la mas reciente no tiene caratula, vale la de otra emision.
            if not de_fila[clave_titulo]['img'] and e['img']:
                de_fila[clave_titulo]['img'] = e['img']
        else:
            de_fila[clave_titulo] = dict(e, n=1)

    filas = []
    for g, nombre in GRUPOS:
        por_canal = {}
        orden = []
        for tarjeta in tarjetas[g].values():
            if tarjeta['canal'] not in por_canal:
                por_canal[tarjeta['canal']] = []
                orden.append(tarjeta['canal'])
            por_canal[tarjeta['canal']].append(tarjeta)
        colas = [por_canal[c] for c in orden]
        elegidas = []
        while colas and (por_grupo is None or len(elegidas) < por_grupo):
            quedan = []
            for cola in colas:
                if por_grupo is not None and len(elegidas) >= por_grupo:
                    break
                elegidas.append(cola.pop(0))
                if cola:
                    quedan.append(cola)
            colas = quedan
        if g == 'peliculas':
            # Una pelicula repetida es la misma pelicula: una tarjeta sin
            # contador, que abre directamente la emision mas reciente, que es
            # la que mas tarda en desaparecer.
            for tarjeta in elegidas:
                tarjeta['n'] = 1
        caratulas.completar(elegidas)
        filas.append({'id': g, 'nombre': nombre, 'items': elegidas})
        if g == 'peliculas':
            filas.extend(filas_de_peliculas(elegidas))
    for fila in filas:
        for tarjeta in fila['items']:
            tarjeta.pop('generos', None)
    return filas


def filas_de_peliculas(peliculas):
    """
    Las filas que van debajo de la de todas las peliculas, como en Netflix:
    las que estan a punto de borrarse y luego una por genero ("Peliculas de
    terror", "Comedias"...). Las tarjetas son copias: la misma pelicula puede
    estar en varias filas.
    """
    filas = []
    limite = timezone.now().timestamp() + ULTIMA_HORAS * 3600
    ultimas = sorted((dict(p) for p in peliculas if p['caduca'] <= limite),
                     key=lambda p: p['caduca'])
    if len(ultimas) >= GENERO_MINIMO:
        filas.append({'id': ULTIMA[0], 'nombre': ULTIMA[1], 'items': ultimas})
    generos = []
    for g, nombre, _ in GENEROS:
        suyas = [dict(p) for p in peliculas if g in p.get('generos', ())]
        if len(suyas) >= GENERO_MINIMO:
            generos.append({'id': g, 'nombre': nombre, 'items': suyas})
    # Las mas llenas primero.
    generos.sort(key=lambda f: -len(f['items']))
    return filas + generos


def emisiones_de(device, grupo, titulo):
    """Todas las emisiones de un titulo (los capitulos de una serie)."""
    from . import caratulas
    buscado = plano(titulo)
    lista = [e for e in emisiones(canales_con_archivo(device))
             if e['grupo'] == grupo and plano(e['titulo']) == buscado]
    for e in lista:
        e.pop('generos', None)
    caratulas.completar(lista)
    return lista


def todas_las_emisiones():
    """Lo emitido de todos los canales con archivo, sin mirar el aparato."""
    from apps.channels.models import Channel
    canales = Channel.objects.filter(is_active=True, has_catchup=True, is_adult=False) \
        .exclude(origen_grabador='').select_related('category')
    return emisiones({c: c.timeshift_hours or 168 for c in canales})
