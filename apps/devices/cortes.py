"""
Cortes de conexion de cada aparato, para verlos en el panel.

Lo pidio soporte el 24/11/2026: a un cliente le salia varias veces "Se ha
perdido la conexion" y no sabiamos por que. Mirando el registro de nginx se
vio que eran caidas de su linea, de noche, y que ningun otro deco las tenia;
pero eso no lo puede mirar soporte cada vez.

Lo cuenta el propio portal: cuando vuelve la red avisa de cuanto ha estado
sin ella (type=stb&action=log&diag=corte <segundos>). Si el cliente apaga o
reinicia el deco en mitad del corte, lo avisa al arrancar otra vez
("corte <segundos> reinicio"). Un corte con muchos reintentos es un solo
aviso. Se guarda una semana en la cache.

Para no dar falsos positivos, la etiqueta roja del listado no cuenta:
  - los cortes cortos (menos de MINIMO s): una peticion lenta suelta que a la
    siguiente ya va, no una linea que se cae;
  - los cortes generales: si en los mismos minutos se cortan GENERAL aparatos
    o mas, el problema es nuestro (servidor o red), no de cada cliente.
Esos se siguen viendo en la ficha, en gris y marcados.
"""
import time
from datetime import datetime, timezone as tz

from django.core.cache import cache

GUARDA = 7 * 24 * 3600
MAXIMO = 100                          # por aparato
MINIMO = 30                           # s: por debajo no cuenta para la etiqueta
GENERAL = 20                          # aparatos cortados en los mismos minutos
VENTANA = 2                           # minutos a cada lado para decir "los mismos"
CLAVE_RECIENTES = 'cortes:recientes'  # {id del aparato: hora del ultimo corte}


def _clave(device_id):
    return 'cortes:aparato:%d' % device_id


def _clave_minuto(minuto):
    return 'cortes:minuto:%d' % minuto


def apuntar(device, segundos, ip='', reinicio=False):
    ahora = time.time()
    segundos = max(0, min(int(segundos), GUARDA))
    inicio = ahora - segundos
    try:
        lista = cache.get(_clave(device.id)) or []
        lista.append({'inicio': inicio, 'dur': segundos, 'ip': ip or '',
                      'reinicio': bool(reinicio)})
        lista = [c for c in lista if c['inicio'] > ahora - GUARDA][-MAXIMO:]
        cache.set(_clave(device.id), lista, GUARDA)
        # Cuantos aparatos empiezan un corte en cada minuto. incr es atomico
        # en Redis: en un corte general llegan cientos a la vez.
        clave = _clave_minuto(int(inicio // 60))
        cache.add(clave, 0, GUARDA)
        cache.incr(clave)
        recientes = cache.get(CLAVE_RECIENTES) or {}
        recientes[device.id] = ahora
        recientes = {k: v for k, v in recientes.items() if v > ahora - GUARDA}
        cache.set(CLAVE_RECIENTES, recientes, GUARDA)
    except Exception:
        pass


def duracion(segundos):
    if segundos < 60:
        return '%d s' % segundos
    if segundos < 3600:
        return '%d min %02d s' % (segundos // 60, segundos % 60)
    return '%d h %02d min' % (segundos // 3600, segundos % 3600 // 60)


def _generales(cortes):
    """Los minutos (de inicio) en los que se cortaron GENERAL aparatos o mas."""
    minutos = set()
    for c in cortes:
        m = int(c['inicio'] // 60)
        minutos.update(range(m - VENTANA, m + VENTANA + 1))
    if not minutos:
        return set()
    try:
        cuentas = cache.get_many([_clave_minuto(m) for m in minutos])
    except Exception:
        return set()
    por_minuto = {m: cuentas.get(_clave_minuto(m)) or 0 for m in minutos}
    generales = set()
    for c in cortes:
        m = int(c['inicio'] // 60)
        if sum(por_minuto.get(x, 0) for x in range(m - VENTANA, m + VENTANA + 1)) >= GENERAL:
            generales.add(m)
    return generales


def _cuenta(c, generales):
    return c['dur'] >= MINIMO and int(c['inicio'] // 60) not in generales


def de(device):
    """Los cortes de un aparato, del mas nuevo al mas viejo, y cuantos en 24 h."""
    try:
        lista = cache.get(_clave(device.id)) or []
    except Exception:
        lista = []
    generales = _generales(lista)
    ahora = time.time()
    salida = []
    for c in sorted(lista, key=lambda c: c['inicio'], reverse=True):
        general = int(c['inicio'] // 60) in generales
        salida.append({
            'cuando': datetime.fromtimestamp(c['inicio'], tz.utc),
            'dur': duracion(c['dur']),
            'ip': c.get('ip', ''),
            'reinicio': c.get('reinicio', False),
            'hoy': c['inicio'] > ahora - 24 * 3600,
            'corto': c['dur'] < MINIMO,
            'general': general,
            'cuenta': _cuenta(c, generales),
        })
    return {'lista': salida,
            'en_24h': sum(1 for c in salida if c['hoy'] and c['cuenta']),
            'en_7d': sum(1 for c in salida if c['cuenta']),
            'minimo': MINIMO}


def de_ids(ids):
    """{id: cortes que cuentan en las ultimas 24 h}, de un golpe."""
    try:
        listas = cache.get_many([_clave(i) for i in ids])
    except Exception:
        return {}
    desde = time.time() - 24 * 3600
    hoy = {i: [c for c in listas.get(_clave(i)) or [] if c['inicio'] > desde and c['dur'] >= MINIMO]
           for i in ids}
    generales = _generales([c for l in hoy.values() for c in l])
    salida = {}
    for i, l in hoy.items():
        n = sum(1 for c in l if _cuenta(c, generales))
        if n:
            salida[i] = n
    return salida


def de_lista(devices):
    return de_ids([d.id for d in devices])


def cuantos_24h():
    """{id: cortes que cuentan} de todos los aparatos con alguno en 24 h."""
    try:
        recientes = cache.get(CLAVE_RECIENTES) or {}
    except Exception:
        return {}
    desde = time.time() - 24 * 3600
    return de_ids([k for k, v in recientes.items() if v > desde])


def con_cortes(horas=24):
    """Los id de los aparatos con algun corte que cuenta en las ultimas 24 h."""
    return list(cuantos_24h())


def generales_24h():
    """
    Los cortes generales (nuestros) de las ultimas 24 h: [{cuando, aparatos}],
    uno por cada racha de minutos seguidos en que se cortaron muchos a la vez.
    """
    ahora = int(time.time() // 60)
    minutos = list(range(ahora - 24 * 60 - VENTANA, ahora + 1))
    try:
        cuentas = cache.get_many([_clave_minuto(m) for m in minutos])
    except Exception:
        return []
    n = {m: cuentas.get(_clave_minuto(m)) or 0 for m in minutos}
    rachas, actual = [], None
    for m in minutos[VENTANA:]:
        cerca = sum(n.get(x, 0) for x in range(m - VENTANA, m + VENTANA + 1))
        if cerca >= GENERAL and n[m]:
            if actual and m - actual['fin'] <= 2 * VENTANA + 1:
                actual['fin'] = m
                actual['aparatos'] += n[m]
            else:
                actual = {'inicio': m, 'fin': m, 'aparatos': n[m]}
                rachas.append(actual)
    return [{'cuando': datetime.fromtimestamp(r['inicio'] * 60, tz.utc), 'aparatos': r['aparatos']}
            for r in reversed(rachas)]


def resumen():
    """Para el dashboard."""
    cuantos = cuantos_24h()
    return {'aparatos': len(cuantos), 'cortes': sum(cuantos.values()),
            'generales': generales_24h(), 'minimo': MINIMO}
