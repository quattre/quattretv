"""
La hora de verdad de cada programa, con la EIT de la propia emision.

Las guias publicadas se equivocan: Telecinco alarga un programa hora y media
y la guia no se entera, y en Neox o Teledeporte van 20-40 minutos desviadas.
La EIT "ahora / siguiente" que viaja con la señal la actualiza la cadena en
directo y va al segundo (medido el 28/10/2026: el "ahora" cambia a los 0-6 s
de la hora que declara). Unos escuchadores en los CDN (deploy/eit/escucha.py)
mandan aqui cada cambio de programa.

En pantalla se sigue viendo la hora de la guia publicada, que es la que la
gente conoce (salvo si la fuente va desviada horas enteras: ver desfases). La de verdad solo se usa por dentro, para que el archivo empiece
donde empieza el programa y no se corte antes de que acabe (ver
handle_archive_link en apps/stalker_api/views.py).
"""
import logging
import re
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.cache import cache

logger = logging.getLogger(__name__)

VENTANA = timedelta(minutes=60)   # cuanto puede desviarse la guia
# Si el titulo se repite (capitulos seguidos de Big Bang Theory), por titulo
# no se sabe cual es: solo se acepta el que esta casi a su hora.
VENTANA_REPETIDO = timedelta(minutes=10)
FRESCO = timedelta(minutes=10)    # un cambio de verdad, no un dato viejo


def _fecha(texto):
    return datetime.strptime(texto, '%Y-%m-%d %H:%M:%S').replace(tzinfo=dt_timezone.utc)


def canales_por_nombre():
    """{nombre en el CDN: canal}. El CDN los llama como su carpeta de HLS."""
    from apps.channels.models import Channel

    try:
        guardado = cache.get('eit:canales')
        if guardado is not None:
            return guardado
    except Exception:
        pass
    canales = {}
    for c in Channel.objects.filter(is_active=True).only('id', 'cdn_name', 'stream_url'):
        if c.cdn_name:
            canales.setdefault(c.cdn_name.lower(), c.id)
        m = re.search(r'/hls/([^/]+)/', c.stream_url or '')
        if m:
            canales.setdefault(m.group(1).lower(), c.id)
    try:
        cache.set('eit:canales', canales, 600)
    except Exception:
        pass
    return canales


def aplicar(cambios):
    """
    Apunta la hora real de los programas que han empezado. Cada cambio es un
    dict con canal (nombre en el CDN), tipo ("AHORA"), inicio y visto (UTC,
    "AAAA-MM-DD hh:mm:ss") y nombre. Devuelve cuantos programas ha tocado.
    Cada cambio se guarda tambien (ObservacionEit), para volver a aplicarlo
    cuando la guia se recarga y para ver si una fuente va desviada.
    """
    from apps.epg.models import ObservacionEit

    canales = canales_por_nombre()
    vistos = []
    for c in cambios:
        try:
            if c.get('tipo') != 'AHORA':
                continue
            inicio, visto = _fecha(c['inicio']), _fecha(c['visto'])
            canal = canales.get((c.get('canal') or '').lower())
        except (KeyError, TypeError, ValueError):
            continue
        # Si lo que dice que ha empezado no acaba de empezar, no es un cambio
        # de programa: À Punt y ETB 2 mandan horas de hace horas.
        if not canal or abs(visto - inicio) > FRESCO:
            continue
        vistos.append(ObservacionEit(channel_id=canal, inicio=inicio, visto=visto,
                                     nombre=(c.get('nombre') or '')[:300]))
    if vistos:
        ObservacionEit.objects.bulk_create(vistos, ignore_conflicts=True)
    tocados = _apuntar(vistos)
    if tocados:
        logger.info('EIT: hora real de %s programas', tocados)
    return tocados


def reaplicar(canales, desde, hasta):
    """
    Vuelve a apuntar la hora real despues de recargar la guia: al recargarla
    los programas se crean de nuevo y, si la fuente ha cambiado la hora de
    alguno, lo de antes no se le pega.
    """
    from apps.epg.models import ObservacionEit
    vistos = list(ObservacionEit.objects.filter(
        channel_id__in=list(canales), inicio__gte=desde - VENTANA, inicio__lte=hasta + VENTANA
    ).order_by('inicio'))
    return _apuntar(vistos)


def _apuntar(vistos):
    from apps.epg.completar import parecido
    from apps.epg.models import Program
    from apps.stalker_api.semana import plano

    tocados = 0
    for o in vistos:
        canal, inicio = o.channel_id, o.inicio
        nombre = plano(o.nombre)
        # Por titulo, nunca solo por hora: si Antena 3 parte un programa en
        # dos, el "siguiente" de la guia no es el que ha empezado.
        candidatos = [p for p in Program.objects.filter(
            channel_id=canal, start_time__gte=inicio - VENTANA, start_time__lte=inicio + VENTANA)
            if parecido(plano(p.title), nombre)]
        if not candidatos:
            continue
        p = min(candidatos, key=lambda x: abs((x.start_time - inicio).total_seconds()))
        if len(candidatos) > 1 and abs(p.start_time - inicio) > VENTANA_REPETIDO:
            continue
        if p.inicio_real != inicio:
            p.inicio_real = inicio
            p.save(update_fields=['inicio_real'])
            tocados += 1
        # El de antes acabo justo entonces.
        anterior = Program.objects.filter(channel_id=canal, start_time__lt=p.start_time) \
            .order_by('-start_time').first()
        if anterior and anterior.fin_real != inicio and \
                abs(anterior.end_time - inicio) <= VENTANA * 2:
            anterior.fin_real = inicio
            anterior.save(update_fields=['fin_real'])
    return tocados


# ---------- Fuentes que van desviadas horas enteras ----------
#
# Tras el cambio de hora del 25/10/2026, open-epg (spain1) seguia con la hora
# de verano: una hora antes en casi todos los canales. Y TCM y Warner venian
# una hora antes en todas las fuentes. Comparado con la EIT el error es justo
# de horas enteras, asi que se ve solo y se corrige al cargar la fuente, cada
# fuente y cada canal por su cuenta. Si la fuente se arregla, la diferencia
# pasa a ser cero y deja de corregirse sola.
HORAS = (-2, -1, 1, 2)
TOLERANCIA = timedelta(minutes=5)       # las guias redondean a 5 minutos
EXACTO = timedelta(minutes=2)           # una sola coincidencia, si es exacta
BUSCAR = timedelta(hours=3, minutes=10)


def _votos(progs, vistos):
    """Diferencias (EIT - fuente) de los titulos que solo salen una vez cerca."""
    from apps.epg.completar import parecido
    from apps.stalker_api.semana import plano
    difs = []
    for o in vistos:
        nombre = plano(o.nombre)
        cerca = [p for p in progs if abs(p.start_time - o.inicio) <= BUSCAR and parecido(plano(p.title), nombre)]
        if len(cerca) == 1:
            difs.append(o.inicio - cerca[0].start_time)
    return difs


def _horas(difs):
    """({horas: votos}, {horas: votos exactos}) de las diferencias que son horas enteras."""
    cuenta, exactos = {}, {}
    for d in difs:
        h = round(d.total_seconds() / 3600)
        if abs(d - timedelta(hours=h)) <= TOLERANCIA:
            cuenta[h] = cuenta.get(h, 0) + 1
            if abs(d - timedelta(hours=h)) <= EXACTO:
                exactos[h] = exactos.get(h, 0) + 1
    return cuenta, exactos


def _desviada(difs, minimo):
    """Las horas que va desviada, si lo va claramente; si no, 0."""
    cuenta, exactos = _horas(difs)
    bien = cuenta.get(0, 0)
    mal = {h: n for h, n in cuenta.items() if h in HORAS}
    if not mal:
        return 0
    h = max(mal, key=lambda k: mal[k])
    if mal[h] >= minimo and mal[h] >= 3 * bien:
        return h
    # Una sola coincidencia vale si es exacta y ninguna otra hora entera, ni
    # la buena, le lleva la contraria: con capitulos seguidos del mismo titulo
    # (Warner, toda la tarde Big Bang) a veces solo hay un titulo unico.
    if minimo <= 2 and mal[h] == 1 and exactos.get(h) == 1 and not bien and len(mal) == 1:
        return h
    return 0


def desfases(programas):
    """
    {canal: timedelta} a sumar a cada canal de una fuente que va desviada horas
    enteras. Se mira canal a canal; si un canal no tiene datos propios, vale
    lo que le pasa a la fuente en general (el error de spain1 era de todos).
    """
    from apps.epg.models import ObservacionEit

    por_canal = {}
    for p in programas:
        por_canal.setdefault(p.channel_id, []).append(p)
    if not por_canal:
        return {}
    desde = min(p.start_time for p in programas) - BUSCAR
    hasta = max(p.start_time for p in programas) + BUSCAR
    vistos = {}
    for o in ObservacionEit.objects.filter(channel_id__in=list(por_canal),
                                           inicio__gte=desde, inicio__lte=hasta):
        vistos.setdefault(o.channel_id, []).append(o)

    resultado, sin_datos, todos = {}, [], []
    for canal, progs in por_canal.items():
        difs = _votos(progs, vistos.get(canal, []))
        todos.extend(difs)
        h = _desviada(difs, 2)
        if h:
            resultado[canal] = timedelta(hours=h)
        elif not _horas(difs)[0].get(0):
            sin_datos.append(canal)
    h = _desviada(todos, 6)
    if h:
        for canal in sin_datos:
            resultado[canal] = timedelta(hours=h)
    return resultado


def tramo_real(programa):
    """(inicio, fin) de verdad de un programa, o los de la guia si no se saben."""
    inicio, fin = programa.start_time, programa.end_time
    # Solo si es razonable: una EIT rara no puede mandar a otro programa.
    if programa.inicio_real and abs(programa.inicio_real - inicio) <= VENTANA:
        inicio = programa.inicio_real
    if programa.fin_real and abs(programa.fin_real - fin) <= VENTANA * 2 and programa.fin_real > inicio:
        fin = programa.fin_real
    elif inicio > programa.start_time:
        # Sin final de verdad (aun no ha empezado el siguiente), si empezo
        # tarde se supone que dura lo de la guia: si no, una peli que empezo
        # una hora tarde se cortaba una hora antes. Si empezo antes no se
        # adelanta el final, que es preferible que sobre a que falte.
        fin = fin + (inicio - programa.start_time)
    return inicio, fin
