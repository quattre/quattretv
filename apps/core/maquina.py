"""
Como esta la maquina que sirve el portal: CPU, memoria, disco y la cola de
peticiones. Se lee de /proc, sin dependencias.

Hace falta verlo desde el panel: el 17/11/2026 el servidor se saturo con 141
decos (una sola CPU al 100 % y 700 peticiones en cola) y lo unico que se veia
era que los decos marcaban "se ha perdido la conexion".
"""
import os
import shutil
import subprocess
import time


def _tiempos_cpu():
    with open('/proc/stat') as f:
        campos = [int(x) for x in f.readline().split()[1:]]
    parado = campos[3] + (campos[4] if len(campos) > 4 else 0)
    return sum(campos), parado


def _cola_peticiones(puerto=8000):
    """Peticiones esperando a que un trabajador las atienda (Recv-Q de ss)."""
    try:
        # El servicio arranca con el PATH del venv y ahi no esta ss: sin la
        # ruta entera la cola salia siempre con un "?".
        ss = shutil.which('ss') or next(
            (r for r in ('/usr/bin/ss', '/usr/sbin/ss', '/bin/ss', '/sbin/ss') if os.path.exists(r)), 'ss')
        salida = subprocess.run([ss, '-ltnH', 'sport = :%d' % puerto],
                                capture_output=True, text=True, timeout=2).stdout
        for linea in salida.splitlines():
            trozos = linea.split()
            if len(trozos) > 2 and trozos[1].isdigit():
                return int(trozos[1])
    except Exception:
        pass
    return None


def estado_maquina():
    datos = {'cpus': os.cpu_count() or 1}
    try:
        t1, p1 = _tiempos_cpu()
        time.sleep(0.25)
        t2, p2 = _tiempos_cpu()
        datos['cpu'] = round(100.0 * (1 - (p2 - p1) / max(1, t2 - t1)))
    except Exception:
        datos['cpu'] = None
    try:
        datos['carga'] = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        datos['carga'] = None
    try:
        mem = {}
        with open('/proc/meminfo') as f:
            for linea in f:
                clave, valor = linea.split(':', 1)
                mem[clave] = int(valor.split()[0])            # kB
        total, libre = mem['MemTotal'], mem.get('MemAvailable', mem['MemFree'])
        datos['mem_total'] = round(total / 1048576.0, 1)      # GB
        datos['mem_usada'] = round((total - libre) / 1048576.0, 1)
        datos['mem'] = round(100.0 * (total - libre) / total)
    except Exception:
        datos['mem'] = None
    try:
        d = shutil.disk_usage('/')
        datos['disco_total'] = round(d.total / 1e9)
        datos['disco_usado'] = round(d.used / 1e9)
        datos['disco'] = round(100.0 * d.used / d.total)
    except Exception:
        datos['disco'] = None
    try:
        with open('/proc/uptime') as f:
            datos['encendida_h'] = round(float(f.read().split()[0]) / 3600, 1)
    except Exception:
        datos['encendida_h'] = None
    datos['cola'] = _cola_peticiones()
    return datos


# --- Historia de las ultimas 24 h ---------------------------------------
#
# La grafica del panel estaba a cero: no habia de donde sacarla. Se apunta
# una muestra cada 5 minutos (decos conectados, CPU y trafico de la tarjeta
# de red) en la cache. No hay cron: la apuntan los propios latidos de los
# decos, y el cerrojo de cache.add hace que solo uno de cada 5 minutos pase.
MUESTRA_CADA = 300
MUESTRAS = 288            # 24 h


def _bytes_red():
    """Bytes recibidos y enviados por todas las tarjetas menos lo."""
    rx = tx = 0
    with open('/proc/net/dev') as f:
        for linea in f.readlines()[2:]:
            nombre, resto = linea.split(':', 1)
            if nombre.strip() == 'lo':
                continue
            campos = resto.split()
            rx += int(campos[0])
            tx += int(campos[8])
    return rx, tx


def apuntar_muestra():
    from datetime import timedelta
    from django.core.cache import cache
    from django.utils import timezone
    try:
        if not cache.add('maquina:muestra:turno', 1, MUESTRA_CADA):
            return
        from apps.devices.models import Device
        ahora = time.time()
        decos = Device.objects.filter(
            last_seen__gte=timezone.now() - timedelta(minutes=5)).count()
        total, parado = _tiempos_cpu()
        rx, tx = _bytes_red()
        antes = cache.get('maquina:contadores')
        cache.set('maquina:contadores', [ahora, total, parado, rx, tx], None)
        cpu = sube = baja = None
        if antes and ahora > antes[0] and total > antes[1] and tx >= antes[4] and rx >= antes[3]:
            seg = ahora - antes[0]
            cpu = round(100.0 * (1 - (parado - antes[2]) / (total - antes[1])))
            sube = round((tx - antes[4]) * 8 / seg / 1e6, 2)      # Mbit/s
            baja = round((rx - antes[3]) * 8 / seg / 1e6, 2)
        historia = cache.get('maquina:historia') or []
        historia.append([int(ahora), decos, cpu, sube, baja])
        cache.set('maquina:historia', historia[-MUESTRAS:], None)
    except Exception:
        pass


def historia_maquina():
    from django.core.cache import cache
    try:
        desde = time.time() - MUESTRAS * MUESTRA_CADA
        return [m for m in (cache.get('maquina:historia') or []) if m[0] >= desde]
    except Exception:
        return []
