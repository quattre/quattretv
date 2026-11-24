"""
Cortes de conexion de cada aparato, para verlos en el panel.

Lo pidio soporte el 24/11/2026: a un cliente le salia varias veces "Se ha
perdido la conexion" y no sabiamos por que. Mirando el registro de nginx se
vio que eran caidas de su linea, de noche, y que ningun otro deco las tenia;
pero eso no lo puede mirar soporte cada vez.

Lo cuenta el propio portal: cuando vuelve la red avisa de cuanto ha estado
sin ella (type=stb&action=log&diag=corte <segundos>). Si el cliente apaga o
reinicia el deco en mitad del corte, lo avisa al arrancar otra vez
("corte <segundos> reinicio"). Se guarda una semana en la cache.
"""
import time
from datetime import datetime, timezone as tz

from django.core.cache import cache

GUARDA = 7 * 24 * 3600
MAXIMO = 100                        # por aparato
CLAVE_RECIENTES = 'cortes:recientes'  # {id del aparato: hora del ultimo corte}


def _clave(device_id):
    return 'cortes:aparato:%d' % device_id


def apuntar(device, segundos, ip='', reinicio=False):
    ahora = time.time()
    segundos = max(0, min(int(segundos), GUARDA))
    try:
        lista = cache.get(_clave(device.id)) or []
        lista.append({'inicio': ahora - segundos, 'dur': segundos, 'ip': ip or '',
                      'reinicio': bool(reinicio)})
        lista = [c for c in lista if c['inicio'] > ahora - GUARDA][-MAXIMO:]
        cache.set(_clave(device.id), lista, GUARDA)
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


def de(device):
    """Los cortes de un aparato, del mas nuevo al mas viejo, y cuantos en 24 h."""
    try:
        lista = cache.get(_clave(device.id)) or []
    except Exception:
        lista = []
    ahora = time.time()
    salida = []
    for c in sorted(lista, key=lambda c: c['inicio'], reverse=True):
        salida.append({
            'cuando': datetime.fromtimestamp(c['inicio'], tz.utc),
            'dur': duracion(c['dur']),
            'ip': c.get('ip', ''),
            'reinicio': c.get('reinicio', False),
            'hoy': c['inicio'] > ahora - 24 * 3600,
        })
    return {'lista': salida, 'en_24h': sum(1 for c in salida if c['hoy']), 'en_7d': len(salida)}


def de_lista(devices):
    """{id: cortes en las ultimas 24 h} para el listado, de un golpe."""
    try:
        listas = cache.get_many([_clave(d.id) for d in devices])
    except Exception:
        return {}
    desde = time.time() - 24 * 3600
    salida = {}
    for d in devices:
        n = sum(1 for c in listas.get(_clave(d.id)) or [] if c['inicio'] > desde)
        if n:
            salida[d.id] = n
    return salida


def con_cortes(horas=24):
    """Los id de los aparatos que han tenido algun corte en esas horas."""
    try:
        recientes = cache.get(CLAVE_RECIENTES) or {}
    except Exception:
        return []
    desde = time.time() - horas * 3600
    return [k for k, v in recientes.items() if v > desde]
