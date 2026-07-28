"""
Avisos de configuración que se ven al desplegar.

`manage.py migrate` y `collectstatic` ejecutan los checks, así que el script de
despliegue enseña estos mensajes cada vez. Son avisos y no errores a propósito:
no queremos que un despliegue se caiga por esto.
"""
from django.conf import settings
from django.core.checks import Warning, register


@register()
def configuracion_de_produccion(app_configs, **kwargs):
    problemas = []

    if settings.DEBUG:
        problemas.append(Warning(
            'DEBUG está activado.',
            hint='Con DEBUG=True cualquier error muestra la traza completa con '
                 'la configuración y fragmentos de código, y Django guarda en '
                 'memoria todas las consultas SQL. Pon DEBUG=False en el .env '
                 'de producción.',
            id='quattretv.W001',
        ))

    if '*' in settings.ALLOWED_HOSTS:
        problemas.append(Warning(
            'ALLOWED_HOSTS acepta cualquier dominio.',
            hint='Pon los dominios reales en ALLOWED_HOSTS del .env, '
                 'p. ej. iptv1.quattre.com,185.25.27.50',
            id='quattretv.W002',
        ))

    if 'django-insecure' in settings.SECRET_KEY:
        problemas.append(Warning(
            'SECRET_KEY es la de por defecto.',
            hint='Genera una y ponla en el .env: los tokens de sesión y los '
                 'enlaces temporales del archivo se firman con ella.',
            id='quattretv.W003',
        ))

    return problemas
