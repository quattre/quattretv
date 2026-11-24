"""
Cortes de conexion de cada aparato: un registro de todos, para el panel.

Lo pidio soporte el 24/11/2026: a un cliente le salia varias veces "Se ha
perdido la conexion" y no sabiamos por que. Mirando el registro de nginx se
vio que eran caidas de su linea, de noche, y que ningun otro deco las tenia;
pero eso no lo puede mirar soporte cada vez. Ahora cada corte se guarda
(CorteConexion) y se ve en Cortes de conexion, en la ficha del aparato y en el
dashboard.

Vienen de dos sitios:
  - el propio portal: cuando vuelve la red avisa de cuanto ha estado sin ella
    (type=stb&action=log&diag=corte <segundos>); si lo reinician en mitad del
    corte, lo avisa al arrancar ("corte <segundos> reinicio"). Exacto.
  - el registro de nginx (importar_registro, cada 15 min por cron): las
    peticiones que el aparato dejo de esperar (499) hasta que vuelve a
    contestar. Sirve para los cortes de antes y para los aparatos que aun no
    llevan el portal que avisa. Si el aparato tambien lo avisa, se queda el
    suyo.
Un corte con muchos reintentos es uno solo.

Que es un corte: el aparato se queda sin poder hablar con el servidor
MINIMO s o mas, desde la primera peticion que se queda sin respuesta (el
portal espera 12 s y saca el aviso) hasta la primera que vuelve a tenerla.
Lo de menos de MINIMO s no es un corte y ni se guarda (casi siempre es una
sola peticion que tardo y a la siguiente ya fue bien, o el deco apagandose);
"sobran", dijo soporte el 24/11/2026.

Los generales se guardan pero aparte: si en los mismos minutos se cortan
GENERAL aparatos o mas, el problema es nuestro (servidor o red), no de cada
cliente, y no se le cuentan a nadie.
"""
import gzip
import logging
import re
from datetime import datetime, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import CorteConexion, Device

log = logging.getLogger(__name__)

MINIMO = 30                          # s: por debajo no cuenta
GENERAL = 20                         # aparatos cortados en los mismos minutos
VENTANA = timedelta(minutes=2)       # "los mismos minutos": tanto a cada lado
JUNTOS = timedelta(minutes=3)        # el mismo corte contado por las dos vias
ESPERA_PORTAL = 12                   # s que espera el portal antes de rendirse
APAGADO = 30 * 60                    # sin pedir nada tanto tiempo: estaba apagado
REBOTE = 120                         # s: un corte que vuelve enseguida es el mismo


def contables(qs):
    return qs.filter(duracion__gte=MINIMO, general=False)


def _marcar_general(inicio):
    qs = CorteConexion.objects.filter(inicio__range=(inicio - VENTANA, inicio + VENTANA))
    if qs.values_list('device_id', 'ip').distinct().count() >= GENERAL:
        qs.filter(general=False).update(general=True)


def _mismo(device, ip, inicio):
    q = Q(device=device) if device else Q()
    if ip:
        q = q | Q(ip=ip) if device else Q(ip=ip)
    if not q:
        return CorteConexion.objects.none()
    return CorteConexion.objects.filter(q, inicio__range=(inicio - JUNTOS, inicio + JUNTOS))


def apuntar(device, segundos, ip='', reinicio=False):
    """Lo que cuenta el portal al volver la red."""
    segundos = max(0, min(int(segundos), 7 * 24 * 3600))
    if segundos < MINIMO:
        return              # no es un corte: ver arriba
    inicio = timezone.now() - timedelta(seconds=segundos)
    try:
        # El mismo corte ya sacado del registro de nginx: vale mas este.
        _mismo(device, ip, inicio).filter(origen='registro').delete()
        CorteConexion.objects.create(device=device, inicio=inicio, duracion=segundos,
                                     ip=ip or None, origen='aparato', reinicio=bool(reinicio))
        _marcar_general(inicio)
    except Exception:
        log.exception('no se ha podido apuntar el corte de %s', device)


def duracion(segundos):
    if segundos < 60:
        return '%d s' % segundos
    if segundos < 3600:
        return '%d min %02d s' % (segundos // 60, segundos % 60)
    return '%d h %02d min' % (segundos // 3600, segundos % 3600 // 60)


def fila(c, ahora=None):
    ahora = ahora or timezone.now()
    return {
        'id': c.id, 'cuando': c.inicio, 'dur': duracion(c.duracion), 'ip': c.ip or '',
        'reinicio': c.reinicio, 'general': c.general, 'corto': c.duracion < MINIMO,
        'cuenta': c.duracion >= MINIMO and not c.general,
        'hoy': c.inicio > ahora - timedelta(hours=24),
        'origen': c.origen, 'device': c.device,
    }


def de(device, cuantos=100):
    """Los cortes de un aparato (los ultimos), y cuantos cuentan en 24 h y 7 dias."""
    ahora = timezone.now()
    qs = CorteConexion.objects.filter(device=device)
    reales = contables(qs)
    n_reales = reales.count()
    return {
        # Solo los de verdad; los cortos y generales, en la pagina de cortes.
        'lista': [fila(c, ahora) for c in reales[:cuantos]],
        'en_24h': reales.filter(inicio__gte=ahora - timedelta(hours=24)).count(),
        'en_7d': reales.filter(inicio__gte=ahora - timedelta(days=7)).count(),
        'total': n_reales,
        'otros': qs.count() - n_reales,
        'minimo': MINIMO,
    }


def cuantos_24h(ids=None):
    """{id del aparato: cortes que cuentan en las ultimas 24 h}."""
    qs = contables(CorteConexion.objects.filter(
        inicio__gte=timezone.now() - timedelta(hours=24), device__isnull=False))
    if ids is not None:
        qs = qs.filter(device_id__in=ids)
    return dict(qs.values_list('device_id').annotate(n=Count('id')).values_list('device_id', 'n'))


def de_lista(devices):
    return cuantos_24h([d.id for d in devices])


def con_cortes(horas=24):
    return list(cuantos_24h())


def generales(desde):
    """Los cortes generales (nuestros): [{cuando, aparatos}], uno por racha."""
    rachas, actual = [], None
    for c in CorteConexion.objects.filter(general=True, inicio__gte=desde).order_by('inicio'):
        if actual and c.inicio - actual['fin'] <= 2 * VENTANA:
            actual['fin'] = c.inicio
            actual['quien'].add((c.device_id, c.ip))
        else:
            actual = {'cuando': c.inicio, 'fin': c.inicio, 'quien': {(c.device_id, c.ip)}}
            rachas.append(actual)
    return [{'cuando': r['cuando'], 'aparatos': len(r['quien'])} for r in reversed(rachas)]


def resumen():
    """Para el dashboard: las ultimas 24 h."""
    desde = timezone.now() - timedelta(hours=24)
    qs = contables(CorteConexion.objects.filter(inicio__gte=desde))
    return {'aparatos': qs.values_list('device_id', 'ip').distinct().count(),
            'cortes': qs.count(), 'generales': generales(desde), 'minimo': MINIMO}


def los_que_mas(qs, cuantos=15):
    """Los aparatos con mas cortes que cuentan en esa seleccion."""
    filas = list(contables(qs).values('device_id', 'device__mac_address', 'device__name',
                                      'device__user__username', 'ip')
                 .annotate(n=Count('id'), total=Sum('duracion')).order_by('-n', '-total')[:cuantos])
    for f in filas:
        f['total_txt'] = duracion(f['total'] or 0)
    return filas


# ---------- Del registro de nginx ----------

# Nuestras maquinas (la plataforma vieja reenvia peticiones de muchos decos, y
# la oficina): sus 499 no son de un cliente.
NUESTRAS = ('185.25.27.',)

LINEA = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "\S+ (\S+)[^"]*" (\d{3}) ')


def _es_api(ruta):
    return '?type=' in ruta and ('/stalker_portal/' in ruta or '/quattretv/stb/' in ruta)


def cortes_del_registro(lineas):
    """
    [(ip, inicio, segundos)] de las lineas de un access.log de nginx, en orden.

    Un corte empieza en la primera peticion al portal que el aparato dejo de
    esperar (499, se rinde a los 12 s) y acaba en la primera que le vuelve a
    contestar. Si despues de rendirse no pide nada en mucho rato, es que lo
    apagaron: el corte acaba ahi.
    """
    abiertos, cerrados, salida = {}, {}, []

    def cerrar(ip):
        c = cerrados.pop(ip)
        salida.append((ip, c['inicio'], max(0, int((c['fin'] - c['inicio']).total_seconds()))))

    for linea in lineas:
        ip = linea[:linea.find(' ')]
        if ip not in abiertos and ' 499 ' not in linea:
            continue
        m = LINEA.match(linea)
        if not m:
            continue
        _, cuando, ruta, estado = m.groups()
        try:
            t = datetime.strptime(cuando, '%d/%b/%Y:%H:%M:%S %z')
        except ValueError:
            continue
        if estado == '499':
            if not _es_api(ruta):
                continue
            if ip in abiertos:
                abiertos[ip]['ultimo'] = t
            elif ip in cerrados and (t - cerrados[ip]['fin']).total_seconds() <= REBOTE:
                abiertos[ip] = cerrados.pop(ip)       # el mismo corte, que sigue
                abiertos[ip]['ultimo'] = t
            else:
                if ip in cerrados:
                    cerrar(ip)
                abiertos[ip] = {'inicio': t - timedelta(seconds=ESPERA_PORTAL), 'ultimo': t}
        elif ip in abiertos:
            c = abiertos.pop(ip)
            apagado = (t - c['ultimo']).total_seconds() > APAGADO
            c['fin'] = c['ultimo'] if apagado else t
            cerrados[ip] = c
    for ip in list(cerrados):
        cerrar(ip)
    return sorted(salida, key=lambda c: c[1])   # los que siguen abiertos, a la proxima


def _abrir(ruta):
    if ruta.endswith('.gz'):
        return gzip.open(ruta, 'rt', errors='replace')
    return open(ruta, errors='replace')


def importar_registro(rutas):
    """Guarda los cortes de esos access.log que no esten ya. Devuelve cuantos."""
    por_ip = {}
    for ip, d in Device.objects.exclude(last_ip=None).values_list('last_ip', 'id'):
        por_ip.setdefault(ip, []).append(d)
    nuevos = 0
    for ruta in rutas:
        with _abrir(ruta) as f:
            cortes = cortes_del_registro(f)
        for ip, inicio, segundos in cortes:
            if ip.startswith(NUESTRAS) or segundos < MINIMO:
                continue
            ids = por_ip.get(ip, [])
            # Con varios aparatos detras de la misma IP no se sabe cual fue:
            # se guarda la IP sola, mejor que culpar al que no es.
            device = Device(id=ids[0]) if len(ids) == 1 else None
            if _mismo(device, ip, inicio).exists():
                continue
            CorteConexion.objects.create(device=device, inicio=inicio, duracion=segundos,
                                         ip=ip, origen='registro')
            _marcar_general(inicio)
            nuevos += 1
    return nuevos
