"""
Límite de intentos para el portal de los decos.

El endpoint del portal tiene que ser abierto (los decos no traen sesión ni
CSRF), así que el login se puede probar en bucle. Esto pone un tope por IP sin
tocar el resto de acciones, que son las que usan los aparatos continuamente.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

LOGIN_MAX_ATTEMPTS = 15
LOGIN_WINDOW_SECONDS = 300


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def too_many_attempts(request, scope='login'):
    """
    True si esta IP se ha pasado de intentos.

    Si la caché no responde se deja pasar: preferimos no bloquear a nadie por
    que Redis esté caído.
    """
    ip = client_ip(request)
    if not ip:
        return False

    key = f'throttle:{scope}:{ip}'
    try:
        attempts = cache.get_or_set(key, 0, LOGIN_WINDOW_SECONDS)
        attempts = cache.incr(key)
    except Exception as exc:
        logger.warning('Throttle sin cache (%s), se deja pasar', exc)
        return False

    if attempts > LOGIN_MAX_ATTEMPTS:
        logger.warning('Demasiados intentos de %s desde %s', scope, ip)
        return True
    return False


def reset_attempts(request, scope='login'):
    """Un acceso correcto limpia el contador de esa IP."""
    ip = client_ip(request)
    if not ip:
        return
    try:
        cache.delete(f'throttle:{scope}:{ip}')
    except Exception:
        pass
