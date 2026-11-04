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
    try:
        guia_desde_eit(vistos)
    except Exception:
        logger.exception('EIT: no se pudo completar la guia')
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


def _raiz(titulo):
    """El nombre de la serie, sin temporada ni episodio: la EIT dice "Caso
    abierto - Temporada 7 - Ep.1 El cruce" y la guia "Caso abierto (T7)"."""
    from apps.stalker_api.semana import plano
    t = re.sub(r'\(.*?\)', '', plano(titulo))
    return re.split(r'\s+-\s+', t)[0].strip(' .:-')


def _apuntar(vistos):
    from apps.epg.completar import parecido
    from apps.epg.models import Program

    tocados = 0
    ultimo = {}   # canal -> (hora de guia, hora real) del ultimo apuntado
    for o in sorted(vistos, key=lambda x: x.inicio):
        canal, inicio = o.channel_id, o.inicio
        nombre = _raiz(o.nombre)
        # Por titulo, nunca solo por hora: si Antena 3 parte un programa en
        # dos, el "siguiente" de la guia no es el que ha empezado.
        candidatos = [p for p in Program.objects.filter(
            channel_id=canal, start_time__gte=inicio - VENTANA, start_time__lte=inicio + VENTANA)
            if parecido(_raiz(p.title), nombre)]
        if not candidatos:
            continue
        p = min(candidatos, key=lambda x: abs((x.start_time - inicio).total_seconds()))
        if len(candidatos) > 1:
            # Dos capitulos seguidos de lo mismo: es el siguiente al ultimo que
            # se vio. Por cercania no vale si el canal va con retraso (Veo7 va
            # media hora tarde): el de las 06:38 se lo llevaba el de las 06:45.
            antes = ultimo.get(canal)
            if antes is None:
                q = Program.objects.filter(
                    channel_id=canal, inicio_real__lt=inicio,
                    inicio_real__gte=inicio - timedelta(hours=6)).order_by('-inicio_real').first()
                antes = (q.start_time, q.inicio_real) if q else None
            siguientes = sorted((c for c in candidatos if antes and c.start_time > antes[0]),
                                key=lambda x: x.start_time)
            if siguientes and inicio - antes[1] >= timedelta(minutes=10):
                p = siguientes[0]
            elif abs(p.start_time - inicio) > VENTANA_REPETIDO:
                continue
        ultimo[canal] = (p.start_time, inicio)
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
        nombre = _raiz(o.nombre)
        cerca = [p for p in progs if abs(p.start_time - o.inicio) <= BUSCAR and parecido(_raiz(p.title), nombre)]
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


def _torcida(difs):
    """
    Si la fuente va siempre desviada lo mismo pero no horas enteras (TCM en
    spain1 y spain2, 71-76 minutos), no es el cambio de hora: son datos malos
    y no se pueden arreglar sumando nada.
    """
    if len(difs) < 3 or _horas(difs)[0]:
        return False
    minutos = sorted(d.total_seconds() / 60 for d in difs)
    return minutos[-1] - minutos[0] <= 15 and abs(minutos[len(minutos) // 2]) >= 30


def desfases(programas):
    """
    {canal: timedelta} a sumar a cada canal de una fuente que va desviada horas
    enteras. Se mira canal a canal; si un canal no tiene datos propios, vale
    lo que le pasa a la fuente en general (el error de spain1 era de todos).
    None si en ese canal la fuente va desviada sin arreglo (ver _torcida).
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
        elif _torcida(difs):
            resultado[canal] = None
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


# ---------- Las horas que se enseñan ----------
#
# La guia de las fuentes va a menudo por detras de lo que se emite: Veo7
# empezaba cada programa 25-35 minutos despues de lo que decia la guia durante
# todo el dia, y Warner o À Punt entre 5 y 20. La EIT dice cuando empezo de
# verdad lo que ya se ha emitido; lo que viene detras suele ir con el mismo
# retraso, asi que se le suma, sin pasar de unas horas: los canales se vuelven
# a poner en hora en algun momento (las noticias, el prime time).
RETRASO_MAX = timedelta(minutes=45)
ARRASTRE = timedelta(hours=4)


def horas_vistas(programas):
    """
    Pone a cada programa .ver_ini y .ver_fin: la hora real si se sabe, si no
    la de la guia con el retraso que llevaba el canal en lo ultimo visto.
    Los programas pueden ser de varios canales; se ordenan por canal y hora.
    """
    from apps.epg.models import Program

    por_canal = {}
    for p in programas:
        por_canal.setdefault(p.channel_id, []).append(p)
    if not por_canal:
        return programas
    for lista in por_canal.values():
        lista.sort(key=lambda x: x.start_time)

    # Lo ultimo visto de cada canal antes de su primer programa, para saber
    # con que retraso llega.
    primero = {c: l[0].start_time for c, l in por_canal.items()}
    previos = {}
    for p in Program.objects.filter(
            channel_id__in=list(por_canal), inicio_real__isnull=False,
            start_time__gte=min(primero.values()) - ARRASTRE,
            start_time__lt=max(primero.values())).order_by('start_time'):
        if p.start_time < primero[p.channel_id]:
            previos[p.channel_id] = p

    for canal, lista in por_canal.items():
        ref = None   # (hora de guia del ultimo visto, retraso)
        previo = previos.get(canal)
        if previo:
            d = previo.inicio_real - previo.start_time
            if abs(d) <= RETRASO_MAX:
                ref = (previo.start_time, d)
        antes = None
        for p in lista:
            real = p.inicio_real if p.inicio_real and abs(p.inicio_real - p.start_time) <= VENTANA else None
            # Al dejar de sumar el retraso, el de antes se quedaria encogido
            # (un Big Bang de 5 minutos): mientras pase eso, se sigue sumando.
            encoge = (antes is not None and antes.end_time == p.start_time and
                      p.start_time - antes.ver_ini < (antes.end_time - antes.start_time) / 2)
            if real:
                p.ver_ini = real
                d = real - p.start_time
                ref = (p.start_time, d) if abs(d) <= RETRASO_MAX else None
            elif ref and (p.start_time - ref[0] <= ARRASTRE or encoge):
                p.ver_ini = p.start_time + ref[1]
            else:
                p.ver_ini = p.start_time
            antes = p
        for i, p in enumerate(lista):
            sig = lista[i + 1] if i + 1 < len(lista) else None
            if p.fin_real and abs(p.fin_real - p.end_time) <= VENTANA * 2 and p.fin_real > p.ver_ini:
                fin = p.fin_real
            elif sig and sig.start_time == p.end_time:
                fin = sig.ver_ini
            else:
                fin = p.end_time + (p.ver_ini - p.start_time)
            p.ver_fin = fin if fin > p.ver_ini else p.end_time
    return programas


def progreso(p, ahora):
    if ahora < p.ver_ini:
        return 0
    if ahora >= p.ver_fin:
        return 100
    return int((ahora - p.ver_ini).total_seconds() * 100 / max(1, (p.ver_fin - p.ver_ini).total_seconds()))


# ---------- Guia hecha con la EIT ----------
#
# Blaze no sale en ninguna fuente gratuita, a Canal 33 y a Buen Viaje la suya
# los dejo de mandar, y salian sin guia. Su señal si dice que empieza y
# cuando: con eso se apunta un programa por cada cambio, y el anterior acaba
# ahi. Lo que viene despues no se sabe; de lo de ahora se supone que dura lo
# que suelen durar en ese canal hasta que la EIT diga que ha empezado otro.
# Solo donde no hay guia de una fuente: esa manda.
EPG_EIT = 'eit'


def _duracion_tipica(canal):
    from apps.epg.models import Program
    durs = sorted((p.end_time - p.start_time) for p in Program.objects.filter(
        channel_id=canal, epg_id=EPG_EIT, fin_real__isnull=False).order_by('-start_time')[:40])
    d = durs[len(durs) // 2] if durs else timedelta(minutes=30)
    return min(max(d, timedelta(minutes=10)), timedelta(hours=2))


def guia_desde_eit(vistos):
    from apps.epg.models import Program
    hechos = 0
    for o in sorted(vistos, key=lambda x: (x.channel_id, x.inicio)):
        canal, inicio = o.channel_id, o.inicio
        if Program.objects.filter(channel_id=canal, start_time__lte=inicio + timedelta(minutes=1),
                                  end_time__gt=inicio).exclude(epg_id=EPG_EIT).exists():
            continue
        # El de antes hecho asi acaba justo ahora.
        Program.objects.filter(channel_id=canal, epg_id=EPG_EIT, start_time__lt=inicio,
                               end_time__gt=inicio - timedelta(hours=3)) \
            .exclude(fin_real__lt=inicio).update(end_time=inicio, fin_real=inicio)
        if Program.objects.filter(channel_id=canal, epg_id=EPG_EIT, start_time=inicio).exists():
            continue
        nombre = (o.nombre or '').strip()
        if nombre.isupper():
            nombre = nombre.capitalize()
        titulo, _, resto = nombre.partition(' - ')
        siguiente = Program.objects.filter(channel_id=canal, start_time__gt=inicio) \
            .order_by('start_time').values_list('start_time', flat=True).first()
        fin = inicio + _duracion_tipica(canal)
        if siguiente and siguiente < fin:
            fin = siguiente
        Program.objects.create(channel_id=canal, epg_id=EPG_EIT, title=titulo[:500] or 'Programa',
                               episode_title=resto[:500], start_time=inicio, end_time=fin,
                               inicio_real=inicio, fin_real=fin if siguiente and siguiente == fin else None)
        hechos += 1
    return hechos
