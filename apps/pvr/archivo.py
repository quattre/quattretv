"""
Qué hay guardado en el archivo de catchup, mirado en el propio disco.

El archivo en MPEG-TS lo escribe dumpstream en <RECORDS_DIR>/archive/<id>/, un
fichero por hora (AAAAmmdd-HH.mpg), y va borrando lo que pasa de su ventana.
Asi que el primer y el ultimo fichero de cada carpeta dicen desde cuando y
hasta cuando se puede ver un canal, y si el ultimo es de esta hora, que se esta
grabando ahora mismo. Se mira por SSH, solo leyendo.
"""
import subprocess
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

from apps.core.ssh import ssh_bin

CONFIG_MINISTRA = '/var/www/stalker_portal/storage/config.php'
CACHE_SECONDS = 300
ESPERA = 30

ORDEN = (
    f'cfg={CONFIG_MINISTRA}; '
    "dir=$(sed -nE \"s/.*define\\('RECORDS_DIR', *'([^']+)'.*/\\1/p\" $cfg)archive; "
    'cd "$dir" 2>/dev/null || exit 3; '
    'for d in */; do '
    "set -- $(ls \"$d\" | grep -E '^[0-9]{8}-[0-9]{2}\\.mpg$' | sed -n '1p;$p'); "
    'echo "${d%/} $1 $2"; '
    'done'
)


def _hora(nombre):
    try:
        return timezone.make_aware(datetime.strptime(nombre[:11], '%Y%m%d-%H'))
    except ValueError:
        return None


def ventanas(storage):
    """
    {id de carpeta: {'desde', 'hasta', 'grabando'}} del archivo de un grabador.

    Devuelve None si no se pudo mirar, para que la pagina lo diga en vez de
    pintar todos los canales como vacios.
    """
    if not storage or not storage.ssh_host:
        return None
    clave = f'archivo:ventanas:{storage.id}'
    try:
        guardado = cache.get(clave)
        if guardado is not None:
            return guardado
    except Exception:
        pass

    try:
        proceso = subprocess.run(
            [ssh_bin(), '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
             '-o', 'ConnectTimeout=8', '-p', str(storage.ssh_port),
             f'{storage.ssh_user}@{storage.ssh_host}', ORDEN],
            capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proceso.returncode != 0:
        return None

    ahora = timezone.now()
    resultado = {}
    for linea in proceso.stdout.splitlines():
        trozos = linea.split()
        if len(trozos) < 3 or not trozos[0].isdigit():
            continue
        desde, ultima = _hora(trozos[1]), _hora(trozos[2])
        if not desde or not ultima:
            continue
        hasta = min(ultima + timedelta(hours=1), ahora)
        resultado[int(trozos[0])] = {
            'desde': desde,
            'hasta': hasta,
            'grabando': ultima >= ahora - timedelta(hours=1, minutes=10),
        }

    try:
        cache.set(clave, resultado, CACHE_SECONDS)
    except Exception:
        pass
    return resultado
