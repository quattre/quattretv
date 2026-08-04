"""
Estado de las máquinas de la plataforma: disco, memoria, carga.

Se recoge por SSH con una sola orden por servidor, sin instalar ningún agente.
Es barato (una conexión cada pocos minutos) y funciona igual en los CDN y en
los grabadores, que es donde duele que se llene un disco sin que nadie mire.
"""
import logging
import subprocess

from django.core.cache import cache

logger = logging.getLogger(__name__)

TIMEOUT = 15
CACHE_SECONDS = 120

# Todo en una orden para no abrir cuatro conexiones.
ORDEN = (
    "df -P -k | tail -n +2; echo '@@'; "
    "cat /proc/loadavg; echo '@@'; "
    "free -k | sed -n 2p; echo '@@'; "
    "nproc; echo '@@'; "
    "cat /proc/uptime"
)

# Sistemas de ficheros que no son discos de verdad (memoria, snaps, pseudo-fs
# del kernel). Sin filtrarlos aparecían cosas como /sys/firmware/efi/efivars,
# que llega a marcar 73 % y no significa nada.
IGNORAR = ('tmpfs', 'devtmpfs', 'overlay', 'squashfs', 'udev', 'efivarfs',
           'none', 'sysfs', 'proc', 'cgroup', 'ramfs')

# Puntos de montaje que tampoco interesan aunque el dispositivo despiste.
MONTAJES_IGNORADOS = ('/sys', '/proc', '/dev', '/run', '/snap')

AVISO_DISCO = 80
CRITICO_DISCO = 90


def estado_servidor(nombre, host, port=22, user='quattre', usar_cache=True):
    """
    Devuelve disco, memoria, carga y uptime de una máquina.

    Nunca lanza: esto se pinta en una página, así que un servidor caído es un
    estado más, no un error.
    """
    clave = f'metricas:{host}:{port}'
    if usar_cache:
        try:
            guardado = cache.get(clave)
            if guardado:
                return guardado
        except Exception:
            pass

    if not host:
        return {'nombre': nombre, 'ok': False, 'error': 'Sin acceso SSH configurado'}

    orden = [
        'ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'ConnectTimeout=8', '-p', str(port), f'{user}@{host}', ORDEN,
    ]

    try:
        proceso = subprocess.run(orden, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        resultado = {'nombre': nombre, 'ok': False, 'error': 'No respondió a tiempo'}
    except OSError as exc:
        resultado = {'nombre': nombre, 'ok': False, 'error': f'No se pudo ejecutar ssh: {exc}'}
    else:
        if proceso.returncode != 0:
            error = (proceso.stderr or '').strip().splitlines()
            resultado = {
                'nombre': nombre, 'ok': False,
                'error': error[-1][:200] if error else 'Fallo al conectar',
            }
        else:
            resultado = _parsear(nombre, proceso.stdout)

    try:
        cache.set(clave, resultado, CACHE_SECONDS)
    except Exception:
        pass

    return resultado


def _parsear(nombre, salida):
    partes = salida.split('@@')
    if len(partes) < 5:
        return {'nombre': nombre, 'ok': False, 'error': 'Respuesta inesperada'}

    datos = {'nombre': nombre, 'ok': True, 'avisos': []}

    # --- discos
    discos = []
    for linea in partes[0].strip().splitlines():
        campos = linea.split()
        if len(campos) < 6 or campos[0].startswith(IGNORAR):
            continue
        if campos[5].startswith(MONTAJES_IGNORADOS):
            continue
        try:
            total_kb, usado_kb = int(campos[1]), int(campos[2])
        except ValueError:
            continue
        if total_kb <= 0:
            continue

        # Se usa el porcentaje que da df, no uno calculado: df descuenta los
        # bloques reservados para root, así que calcularlo a mano da un número
        # más bajo que el que ve cualquiera en consola.
        try:
            pct = int(campos[4].rstrip('%'))
        except (ValueError, IndexError):
            pct = round(usado_kb * 100 / total_kb)
        disco = {
            'montaje': campos[5],
            'total_gb': round(total_kb / 1024 / 1024, 1),
            'usado_gb': round(usado_kb / 1024 / 1024, 1),
            'libre_gb': round((total_kb - usado_kb) / 1024 / 1024, 1),
            'pct': pct,
            'nivel': 'critico' if pct >= CRITICO_DISCO else 'aviso' if pct >= AVISO_DISCO else 'ok',
        }
        discos.append(disco)
        if disco['nivel'] != 'ok':
            datos['avisos'].append(
                f"{disco['montaje']} al {pct}% ({disco['libre_gb']} GB libres)"
            )
    datos['discos'] = sorted(discos, key=lambda d: -d['pct'])

    # --- carga
    try:
        carga = [float(x.replace(',', '.')) for x in partes[1].split()[:3]]
    except (ValueError, IndexError):
        carga = []
    datos['carga'] = carga

    # --- memoria
    try:
        campos = partes[2].split()
        total_kb, usado_kb = int(campos[1]), int(campos[2])
        datos['ram'] = {
            'total_gb': round(total_kb / 1024 / 1024, 1),
            'usado_gb': round(usado_kb / 1024 / 1024, 1),
            'pct': round(usado_kb * 100 / total_kb) if total_kb else 0,
        }
        if datos['ram']['pct'] >= 90:
            datos['avisos'].append(f"Memoria al {datos['ram']['pct']}%")
    except (ValueError, IndexError):
        datos['ram'] = None

    # --- cores y carga relativa
    try:
        datos['cores'] = int(partes[3].strip())
    except ValueError:
        datos['cores'] = 0

    if carga and datos['cores']:
        datos['carga_pct'] = round(carga[0] * 100 / datos['cores'])
        if datos['carga_pct'] >= 90:
            datos['avisos'].append(f"Carga al {datos['carga_pct']} % de la CPU")
    else:
        datos['carga_pct'] = None

    # --- uptime
    try:
        datos['uptime_dias'] = int(float(partes[4].split()[0]) / 86400)
    except (ValueError, IndexError):
        datos['uptime_dias'] = None

    return datos


def estado_de_varios(servidores):
    """
    servidores: lista de (nombre, host, puerto, usuario, etiqueta)

    Se consultan en paralelo: en serie, con varias máquinas lentas, la página
    tardaría demasiado.
    """
    from concurrent.futures import ThreadPoolExecutor

    servidores = list(servidores)
    if not servidores:
        return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        resultados = list(pool.map(
            lambda s: estado_servidor(s[0], s[1], s[2], s[3]), servidores
        ))

    for resultado, servidor in zip(resultados, servidores):
        resultado['etiqueta'] = servidor[4]
    return resultados
