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
