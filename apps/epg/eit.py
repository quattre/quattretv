"""
La hora de verdad de cada programa, con la EIT de la propia emision.

Las guias publicadas se equivocan: Telecinco alarga un programa hora y media
y la guia no se entera, y en Neox o Teledeporte van 20-40 minutos desviadas.
La EIT "ahora / siguiente" que viaja con la señal la actualiza la cadena en
directo y va al segundo (medido el 28/10/2026: el "ahora" cambia a los 0-6 s
de la hora que declara). Unos escuchadores en los CDN (deploy/eit/escucha.py)
mandan aqui cada cambio de programa.

En pantalla se sigue viendo la hora de la guia publicada, que es la que la
gente conoce. La de verdad solo se usa por dentro, para que el archivo empiece
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
    """
    from apps.epg.completar import parecido
    from apps.epg.models import Program
    from apps.stalker_api.semana import plano

    canales = canales_por_nombre()
    tocados = 0
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
        nombre = plano(c.get('nombre', ''))
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
    if tocados:
        logger.info('EIT: hora real de %s programas', tocados)
    return tocados


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
