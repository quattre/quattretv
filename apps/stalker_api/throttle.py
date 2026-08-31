"""
Límite de intentos para el portal de los decos.

El endpoint del portal tiene que ser abierto (los decos no traen sesión ni
CSRF), así que el login se puede probar en bucle. Esto pone un tope por IP sin
tocar el resto de acciones, que son las que usan los aparatos continuamente.
"""
import ipaddress
import logging
import os

from django.core.cache import cache

logger = logging.getLogger(__name__)

LOGIN_MAX_ATTEMPTS = 15
LOGIN_WINDOW_SECONDS = 300


def _redes_exentas():
    """
    Redes que no cuentan para el limite de intentos.

    Existe por el equipo de revision de LG, que prueba las apps desde Corea. Si
    el revisor teclea mal la contraseña un par de veces se llevaria un
    "Demasiados intentos", daria la app por rota y la rechazaria -- y nosotros
    no nos enteramos de por que. Su propio formulario avisa de que hay que
    dejarles paso.

    La lista viaja en el .env y no en el codigo porque LG la cambia cada cierto
    tiempo, y no queremos un despliegue para eso. El fichero
    deploy/ips_revision_lg.txt tiene la de agosto de 2026 lista para pegar.

    Se admite tanto "1.2.3.4" como "1.2.3.0/24" como "1.2.3.4-1.2.3.9".
    """
    crudo = os.environ.get('IPS_REVISION_LG', '')
    redes = []
    # Primero por lineas y luego por comas, en ese orden: al reves, una linea de
    # comentario que llevara una coma se partia en dos y la segunda mitad ya no
    # empezaba por '#', asi que se intentaba leer como si fuera una IP.
    trozos = []
    for linea in crudo.splitlines():
        linea = linea.split('#')[0]
        trozos.extend(t.strip() for t in linea.replace(';', ',').split(','))
    for trozo in trozos:
        if not trozo:
            continue
        try:
            if '-' in trozo:
                desde, hasta = (t.strip() for t in trozo.split('-', 1))
                redes.extend(ipaddress.summarize_address_range(
                    ipaddress.ip_address(desde), ipaddress.ip_address(hasta)))
            else:
                redes.append(ipaddress.ip_network(trozo, strict=False))
        except ValueError:
            logger.warning('IPS_REVISION_LG: no entiendo "%s", se ignora', trozo)
    return redes


# Se resuelve una vez: son unas pocas redes y no cambian en caliente.
REDES_EXENTAS = _redes_exentas()


def esta_exenta(ip):
    """¿Esta IP se libra del limite de intentos?"""
    if not REDES_EXENTAS or not ip:
        return False
    try:
        dir_ip = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(dir_ip in red for red in REDES_EXENTAS)


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
    if esta_exenta(ip):
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
