"""
Ordenes que se le mandan a un aparato desde el panel: recargar el portal o
reiniciarlo.

El aparato no se puede llamar: es el quien pregunta. Ya lo hace cada minuto
(el latido del portal, type=watchdog), asi que la orden se deja en la cache y
se le entrega en su siguiente latido. Si esta apagado, la recoge al encender
mientras no caduque.

Para recargar todos los decos de golpe (tras cambiar el portal, por ejemplo)
no se apunta una orden por aparato: se guarda la hora de la recarga general, y
cada deco cuyo portal se cargo antes de esa hora se recarga. El portal manda
en cada latido cuando se cargo.
"""
import time

from django.core.cache import cache

EVENTOS = {
    'recargar': 'Recargar el portal',
    'reiniciar': 'Reiniciar el aparato',
}
CADUCA = 24 * 3600
CLAVE_GENERAL = 'evento:recarga_general'
# Solo los decos: las apps de las teles estan en revision y no se tocan.
TIPOS_RECARGA_GENERAL = ('mag',)


def _clave(device):
    return f'evento:aparato:{device.id}'


def pedir(device, evento):
    """True si la orden queda apuntada; False si la cache no responde."""
    if evento not in EVENTOS:
        raise ValueError(evento)
    try:
        cache.set(_clave(device), evento, CADUCA)
    except Exception:
        return False
    return True


def pedir_recarga_general():
    try:
        cache.set(CLAVE_GENERAL, int(time.time()), CADUCA * 7)
    except Exception:
        return False
    return True


def recoger(device, cargado=None):
    """La orden pendiente para este aparato, o None. Se entrega una sola vez."""
    try:
        evento = cache.get(_clave(device))
        if evento:
            cache.delete(_clave(device))
            return evento
        general = cache.get(CLAVE_GENERAL)
    except Exception:
        return None
    if (general and cargado and device.device_type in TIPOS_RECARGA_GENERAL
            and int(cargado) < int(general)):
        return 'recargar'
    return None
