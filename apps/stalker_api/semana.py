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
PAGINA = 20
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

# ---------- Como en Netflix y Prime Video ----------
#
# Arriba las pestañas y en cada una filas por genero, en vez de una fila de
# 590 peliculas. El genero lo trae dobleM detras del tipo: "Cine,Terror",
# "Documentales,Naturaleza", "Entretenimiento,Humor" (ver apps/epg/completar.py).
PESTANAS = [
    ('inicio', 'Inicio'),
    ('peliculas', 'Peliculas'),
    ('series', 'Series'),
    ('infantil', 'Infantil'),
    ('documentales', 'Documentales'),
    ('entretenimiento', 'Programas'),
    ('actualidad', 'Noticias y deportes'),
]
# (id, palabras, nombre de la fila en peliculas, en series)
FICCION_ETIQUETAS = [
    ('terror', ('terror', 'horror'), 'Peliculas de terror', 'Series de terror'),
    ('accion', ('accion', 'action', 'aventura', 'adventure', 'belic'),
     'Accion y aventuras', 'Series de accion'),
    ('comedia', ('comedia', 'comedy', 'humor'), 'Comedias', 'Series de comedia'),
    ('suspense', ('thriller', 'suspense', 'policiac', 'crimen', 'crime', 'intriga', 'misterio'),
     'Suspense y policiacas', 'Policiacas y de suspense'),
    ('drama', ('drama',), 'Dramas', 'Series de drama'),
    ('romantico', ('romant', 'romance', 'telenovela'), 'Romanticas', 'Telenovelas y romanticas'),
    ('ficcion', ('ciencia ficcion', 'sci-fi', 'fantas'),
     'Ciencia ficcion y fantasia', 'Ciencia ficcion y fantasia'),
    ('familiar', ('animacion', 'familiar', 'infantil'), 'Animacion y familiares', 'Series de animacion'),
    ('oeste', ('oeste', 'western'), 'Oeste', 'Oeste'),
    ('docu', ('document',), 'Cine documental', 'Series documentales'),
]
ETIQUETAS = {
    'peliculas': [(i, p, peli) for i, p, peli, _ in FICCION_ETIQUETAS],
    'series': [(i, p, serie) for i, p, _, serie in FICCION_ETIQUETAS],
    'documentales': [
        ('naturaleza', ('naturaleza', 'animal', 'nature', 'fauna'), 'Naturaleza y animales'),
        ('historia', ('historia', 'history', 'arqueolog'), 'Historia'),
        ('viajes', ('viaje', 'travel', 'turismo'), 'Viajes'),
        ('ciencia', ('ciencia', 'tecnolog', 'science', 'espacio'), 'Ciencia y tecnologia'),
        ('caza', ('caza', 'pesca'), 'Caza y pesca'),
        ('motor', ('motor', 'coche'), 'Motor'),
        ('sociedad', ('sociedad', 'reportaje', 'actualidad', 'investigacion'), 'Sociedad y reportajes'),
    ],
    'entretenimiento': [
        ('humor', ('humor', 'comedia'), 'Humor'),
        ('concursos', ('concurso',), 'Concursos'),
        ('cocina', ('cocina', 'gastronom'), 'Cocina'),
        ('reality', ('reality', 'telerrealidad'), 'Telerrealidad'),
        ('magacin', ('magaz', 'magacin'), 'Magacines'),
        ('musica', ('music', 'musica'), 'Musica'),
    ],
    'infantil': [
        ('preescolar', ('preescolar',), 'Preescolar'),
        ('dibujos', ('dibujos', 'animacion'), 'Dibujos animados'),
    ],
}
# La ultima fila de cada pestaña: lo que no tiene genero.
OTRAS = {'peliculas': 'Mas peliculas', 'series': 'Mas series', 'infantil': 'Mas infantil',
         'documentales': 'Mas documentales', 'entretenimiento': 'Mas programas'}
FILA_MINIMA = 3          # con menos tarjetas una fila no merece la pena
ULTIMA_HORAS = 24        # "Ultima oportunidad": lo que se borra antes de eso
DESTACADOS = 40          # tarjetas de cada fila de Inicio
TERMINADO = 0.92         # visto hasta aqui, ya no sale en "Seguir viendo"

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


def etiquetas_de(grupo, categoria):
    """El genero dentro del tipo: ('peliculas', 'Cine,Terror') -> ['terror']."""
    lista = ETIQUETAS.get(grupo)
    if not lista:
        return []
    partes = plano(categoria).split(',', 1)
    # "Cine,Terror" o "Peliculas de terror": el genero va detras del tipo.
    texto = partes[1] if len(partes) > 1 else partes[0]
    if texto.strip() in ('cine', 'pelicula', 'peliculas', 'film', 'movie', 'serie', 'series', ''):
        return []
    return [i for i, palabras, _ in lista if any(p in texto for p in palabras)]


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


def _emision(canal, p, horas, tipo_canal):
    """Una emision del archivo como tarjeta, o None si no vale la pena ofrecerla."""
    from apps.epg.completar import generico

    minutos = int((p.end_time - p.start_time).total_seconds() // 60)
    titulo = sin_temporada(p.title)
    # "Cine" o "Documental" a secas no dicen que es: mejor no ofrecerlo.
    if minutos < DURACION_MINIMA_INFANTIL or not titulo or generico(titulo):
        return None
    grupo, seguro = grupo_de(titulo, p.category, minutos, p.year, tipo_canal)
    if not grupo:
        return None
    return {
        'seguro': seguro,
        'grupo': grupo,
        'titulo': titulo,
        'sub': p.episode_title or '',
        'descr': (p.description or '')[:300],
        '_cat': p.category or '',
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
    }


def _corregir(e, corregidos, con_ocultos=False):
    """Aplica lo corregido a mano en el panel. False si hay que quitarla."""
    c = corregidos.get(plano(e['titulo']))
    if c:
        if c.oculto and not con_ocultos:
            return False
        if c.grupo:
            e['grupo'] = c.grupo
        if c.imagen:
            e['img'] = c.imagen
    return True


def emisiones(canales, con_ocultos=False):
    """Lo ya emitido que sigue en el archivo de esos canales, lo mas nuevo antes."""
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
            e = _emision(canal, p, horas, tipo_canal)
            if not e:
                continue
            if e['seguro']:
                seguros.setdefault(plano(e['titulo']), e['grupo'])
            salida.append(e)

    # Big Bang en Neox salia como entretenimiento, porque la guia no lo dice y
    # Neox es un canal de entretenimiento; en Warner, que es de series, si se
    # sabe. Lo que se sabe de un titulo vale para todas sus emisiones.
    for e in salida:
        if not e.pop('seguro'):
            e['grupo'] = seguros.get(plano(e['titulo']), e['grupo'])

    # Lo que se ha corregido a mano en el panel manda sobre lo adivinado.
    _, corregidos = correcciones()
    if corregidos:
        salida = [e for e in salida if _corregir(e, corregidos, con_ocultos)]

    salida = [e for e in salida
              if e['min'] >= DURACION_MINIMA or e['grupo'] == 'infantil']
    conocidas = categorias_conocidas()
    for e in salida:
        cat = e.pop('_cat')
        e['etiquetas'] = etiquetas_de(e['grupo'], cat) or \
            etiquetas_de(e['grupo'], conocidas.get(plano(e['titulo']), ''))
    salida.sort(key=lambda e: -e['ini'])
    return salida


def categorias_conocidas():
    """
    {titulo: categoria con genero} de toda la guia, tambien lo que esta por
    emitir. La guia complementaria solo trae genero de hoy en adelante, pero
    las peliculas se repiten en la semana: lo emitido el lunes sin genero lo
    toma de la emision del jueves.
    """
    from apps.epg.models import Program

    try:
        guardado = cache.get('semana:categorias')
        if guardado is not None:
            return guardado
    except Exception:
        pass
    try:
        conocidas = dict(cache.get('epg:generos') or {})    # ver apps/epg/completar.py
    except Exception:
        conocidas = {}
    for titulo, categoria in Program.objects.filter(
            category__contains=',', start_time__gte=timezone.now() - timedelta(days=8)) \
            .values_list('title', 'category'):
        conocidas[plano(sin_temporada(titulo))] = categoria
    try:
        cache.set('semana:categorias', conocidas, 1800)
    except Exception:
        pass
    return conocidas


def catalogo(device):
    """
    {tipo: tarjetas} de lo que este aparato puede ver. Cada tarjeta es un
    titulo: si se ha emitido varias veces (los capitulos de una serie, los
    telediarios) se juntan y la tarjeta lleva la emision mas reciente y
    cuantas hay. Las pestañas y sus filas se arman con esto (ver pestana).
    """
    canales = canales_con_archivo(device)
    if not canales:
        return {}

    firma = ','.join(f'{c.id}:{h}' for c, h in sorted(canales.items(), key=lambda x: x[0].id))
    clave = 'semana:v2:%s:%s' % (version(), hashlib.md5(firma.encode()).hexdigest())
    try:
        guardado = cache.get(clave)
        if guardado is not None:
            return guardado
    except Exception:
        pass

    ocultas, _ = correcciones()
    resultado = {f['id']: f['items'] for f in filas_de(emisiones(canales))
                 if f['items'] and f['id'] not in ocultas}
    try:
        cache.set(clave, resultado, CACHE_SEGUNDOS)
    except Exception:
        pass
    return resultado


def pestanas(tarjetas):
    """Las pestañas que tienen algo."""
    tiene = {g for g, lista in tarjetas.items() if lista}
    tiene.add('inicio')
    if tiene & {'noticias', 'deportes'}:
        tiene.add('actualidad')
    return [[p, nombre] for p, nombre in PESTANAS if p in tiene]


def pestana(device, nombre):
    """Las filas enteras de una pestaña. Inicio empieza por "Seguir viendo"."""
    tarjetas = catalogo(device)
    filas = []
    if nombre == 'inicio':
        seguir = seguir_viendo(device)
        if seguir:
            filas.append({'id': 'seguir', 'nombre': 'Seguir viendo', 'items': seguir})
    return filas + filas_de_pestana(tarjetas, nombre)


def primeras(filas):
    """Las filas con sus primeras tarjetas y cuantas tiene cada una."""
    return [dict(f, items=f['items'][:PAGINA], total=len(f['items'])) for f in filas]


def mas_de_fila(device, nombre, fila, desde):
    for f in pestana(device, nombre):
        if f['id'] == fila:
            return f['items'][desde:desde + PAGINA]
    return []


def ultima(lista):
    """Lo que el archivo borra en menos de ULTIMA_HORAS, lo mas urgente antes."""
    limite = timezone.now().timestamp() + ULTIMA_HORAS * 3600
    return sorted((t for t in lista if t['caduca'] <= limite), key=lambda t: t['caduca'])


def filas_de_pestana(tarjetas, nombre):
    def de(*grupos):
        return [t for g in grupos for t in tarjetas.get(g, [])]

    def recientes(lista):
        return sorted(lista, key=lambda t: -t['ini'])

    nombres = dict(GRUPOS)
    if nombre == 'inicio':
        # Como la portada de Netflix: un poco de todo, y lo de cada tipo
        # entero en su pestaña.
        filas = [
            ('populares', 'Lo mas visto', populares(tarjetas)),
            ('novedades', 'Novedades', recientes(de('peliculas', 'series', 'documentales'))[:DESTACADOS]),
            ('ultima', 'Ultima oportunidad', ultima(de('peliculas', 'documentales'))[:DESTACADOS]),
            ('reir', 'Para reir', recientes(
                [t for t in de('peliculas', 'series', 'entretenimiento')
                 if {'comedia', 'humor'} & set(t['etiquetas'])])[:DESTACADOS]),
        ]
        filas += [('todo-' + g, nombres[g], tarjetas.get(g, [])[:DESTACADOS]) for g, _ in GRUPOS]
    elif nombre == 'actualidad':
        filas = [(g, nombres[g], tarjetas.get(g, [])) for g in ('noticias', 'deportes')]
    else:
        lista = tarjetas.get(nombre, [])
        filas = []
        if nombre == 'peliculas':
            filas.append(('ultima', 'Ultima oportunidad', ultima(lista)))
        if nombre == 'series':
            filas.append(('novedades', 'Novedades', recientes(lista)[:DESTACADOS]))
        generos = []
        for i, _, nombre_fila in ETIQUETAS.get(nombre, []):
            suyas = [t for t in lista if i in t['etiquetas']]
            if len(suyas) >= FILA_MINIMA:
                generos.append((i, nombre_fila, suyas))
        # Las mas llenas primero. Una pelicula puede estar en dos.
        generos.sort(key=lambda f: -len(f[2]))
        filas += generos
        con_fila = {i for i, _, _ in generos}
        if generos:
            filas.append(('otras', OTRAS.get(nombre, 'Mas'),
                          [t for t in lista if not con_fila & set(t['etiquetas'])]))
        else:
            filas.append(('todo', nombres.get(nombre, ''), lista))
    return [{'id': i, 'nombre': n, 'items': items} for i, n, items in filas
            if len(items) >= FILA_MINIMA or (i in ('todo', 'otras', 'noticias', 'deportes') and items)]


def filas_de(lista, por_grupo=POR_GRUPO):
    """
    Junta las emisiones en tarjetas, una por titulo, y las reparte por tipo.

    Cada tipo se llena por turnos de canal: lo ultimo de cada canal, luego lo
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
            # Y el genero, igual: la guia complementaria solo trae una semana.
            if not de_fila[clave_titulo]['etiquetas'] and e['etiquetas']:
                de_fila[clave_titulo]['etiquetas'] = e['etiquetas']
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
            # contador, que abre la emision mas reciente, que es la que mas
            # tarda en desaparecer.
            for tarjeta in elegidas:
                tarjeta['n'] = 1
        caratulas.completar(elegidas)
        filas.append({'id': g, 'nombre': nombre, 'items': elegidas})
    return filas


def emisiones_de(device, grupo, titulo):
    """Todas las emisiones de un titulo (los capitulos de una serie)."""
    from . import caratulas
    buscado = plano(titulo)
    lista = [e for e in emisiones(canales_con_archivo(device))
             if e['grupo'] == grupo and plano(e['titulo']) == buscado]
    caratulas.completar(lista)
    return lista


# ---------- "Mas como esta" ----------

def similares(device, grupo, titulo, maximo=20):
    """
    Lo parecido a un titulo, para su ficha: del mismo tipo y con generos en
    comun, y a igualdad, del mismo canal y de una epoca parecida.
    """
    lista = catalogo(device).get(grupo, [])
    buscado = plano(titulo)
    ref = next((t for t in lista if plano(t['titulo']) == buscado), None)
    if not ref:
        return []
    mias = set(ref['etiquetas'])
    puntuadas = []
    for t in lista:
        if plano(t['titulo']) == buscado:
            continue
        comunes = len(mias & set(t['etiquetas']))
        if mias and not comunes:
            continue
        puntos = comunes * 10 + (3 if t['canal'] == ref['canal'] else 0)
        if ref['anio'] and t['anio']:
            puntos -= min(5, abs(int(ref['anio']) - int(t['anio'])) // 10)
        puntuadas.append((puntos, t['ini'], t))
    puntuadas.sort(key=lambda x: (-x[0], -x[1]))
    return [t for _, _, t in puntuadas[:maximo]]


# ---------- "Seguir viendo" y "Lo mas visto" ----------

def guardar_progreso(device, ch_id, ini, pos, dur):
    """Por donde va este aparato en un programa del archivo."""
    from datetime import datetime, timezone as dt_timezone
    from apps.channels.models import Channel
    from apps.epg.models import ProgresoArchivo

    # Unos segundos no es haberlo empezado, y antes del inicio (se puede ir
    # 15 minutos antes de la hora de la guia) aun no ha empezado.
    if pos < 120 or dur <= 0:
        return False
    canal = Channel.objects.filter(id=ch_id).first()
    if not canal:
        return False
    inicio = datetime.fromtimestamp(ini, dt_timezone.utc)
    ProgresoArchivo.objects.update_or_create(
        device=device, channel=canal, inicio=inicio,
        defaults={'posicion': min(pos, dur), 'duracion': dur})
    # Lo que el archivo ya ha borrado no sirve ni para "Lo mas visto".
    ProgresoArchivo.objects.filter(device=device, inicio__lt=timezone.now() - timedelta(days=8)).delete()
    return True


def tarjeta_de(canal, programa, horas):
    """La tarjeta de una emision suelta, con las correcciones del panel."""
    tipo_canal = canal.category.name if canal.category else ''
    e = _emision(canal, programa, horas, tipo_canal)
    if not e:
        return None
    e.pop('seguro')
    _, corregidos = correcciones()
    if not _corregir(e, corregidos):
        return None
    e['etiquetas'] = etiquetas_de(e['grupo'], e.pop('_cat'))
    e['n'] = 1
    return e


def seguir_viendo(device, maximo=20):
    """Lo que este aparato dejo a medias y sigue en el archivo, lo ultimo antes."""
    from apps.epg.models import Program, ProgresoArchivo
    from . import caratulas

    if not getattr(device, 'pk', None):
        return []
    canales = {c.id: (c, h) for c, h in canales_con_archivo(device).items()}
    ahora = timezone.now()
    salida = []
    for pr in ProgresoArchivo.objects.filter(device=device)[:60]:
        if pr.posicion >= pr.duracion * TERMINADO or pr.channel_id not in canales:
            continue
        canal, horas = canales[pr.channel_id]
        if pr.inicio < ahora - timedelta(hours=horas):
            continue
        p = Program.objects.filter(channel=canal, start_time=pr.inicio).first()
        e = tarjeta_de(canal, p, horas) if p else None
        if e:
            e.update(pos=pr.posicion, dur=pr.duracion)
            salida.append(e)
            if len(salida) >= maximo:
                break
    caratulas.completar(salida)
    return salida


def populares(tarjetas, maximo=20):
    """
    Lo que mas aparatos han visto del archivo esta semana. Hacen falta al
    menos dos: lo que ve una sola casa no es "lo mas visto".
    """
    from django.db.models import Count
    from apps.epg.models import Program, ProgresoArchivo

    clave = 'semana:populares'
    try:
        cuenta = cache.get(clave)
    except Exception:
        cuenta = None
    if cuenta is None:
        cuenta = {}
        vistos = (ProgresoArchivo.objects.filter(actualizado__gte=timezone.now() - timedelta(days=7))
                  .values('channel_id', 'inicio').annotate(n=Count('device', distinct=True))
                  .order_by('-n')[:100])
        for v in vistos:
            p = Program.objects.filter(channel_id=v['channel_id'], start_time=v['inicio']) \
                .only('title').first()
            if p:
                k = plano(sin_temporada(p.title))
                cuenta[k] = cuenta.get(k, 0) + v['n']
        try:
            cache.set(clave, cuenta, 600)
        except Exception:
            pass
    elegidas = [t for g in ('peliculas', 'series', 'documentales', 'infantil', 'entretenimiento')
                for t in tarjetas.get(g, []) if cuenta.get(plano(t['titulo']), 0) >= 2]
    elegidas.sort(key=lambda t: -cuenta[plano(t['titulo'])])
    return elegidas[:maximo]


def todas_las_emisiones():
    """Lo emitido de todos los canales con archivo, sin mirar el aparato."""
    from apps.channels.models import Channel
    canales = Channel.objects.filter(is_active=True, has_catchup=True, is_adult=False) \
        .exclude(origen_grabador='').select_related('category')
    return emisiones({c: c.timeshift_hours or 168 for c in canales})
