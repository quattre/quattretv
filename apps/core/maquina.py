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
        r1, h1 = _bytes_red(), time.time()
        time.sleep(0.5)
        t2, p2 = _tiempos_cpu()
        r2, h2 = _bytes_red(), time.time()
        datos['cpu'] = round(100.0 * (1 - (p2 - p1) / max(1, t2 - t1)))
        datos['red_baja'] = round((r2[0] - r1[0]) * 8 / (h2 - h1) / 1e6, 1)   # Mbit/s que entran
        datos['red_sube'] = round((r2[1] - r1[1]) * 8 / (h2 - h1) / 1e6, 1)   # Mbit/s que salen
    except Exception:
        datos['cpu'] = None
        datos.setdefault('red_baja', None)
        datos.setdefault('red_sube', None)
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


def _programa(nombre):
    """El servicio arranca con el PATH del venv: los programas, por su ruta."""
    return shutil.which(nombre) or next(
        (r for r in ('/usr/bin/' + nombre, '/usr/sbin/' + nombre, '/bin/' + nombre)
         if os.path.exists(r)), nombre)


def _bytes_salida_cdn(cdn):
    """
    Bytes que ha enviado un CDN por su tarjeta de salida, o None.

    Solo lee /proc/net/dev por ssh: en el CDN no se instala ni se cambia nada.
    Tiene dos tarjetas en marcha, la del multicast (que casi solo recibe) y la
    publica, por la que sale el video a los clientes: es la que mas envia.
    """
    return _bytes_salida(cdn.ssh_host, cdn.ssh_port, cdn.ssh_user)


def _bytes_salida(host, puerto, usuario):
    if not host:
        return None
    try:
        salida = subprocess.run(
            [_programa('ssh'), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=4',
             '-o', 'StrictHostKeyChecking=accept-new', '-p', str(puerto),
             '%s@%s' % (usuario, host), 'cat /proc/net/dev'],
            capture_output=True, text=True, timeout=10).stdout
        mayor = None
        for linea in salida.splitlines()[2:]:
            nombre, resto = linea.split(':', 1)
            if nombre.strip() == 'lo':
                continue
            tx = int(resto.split()[8])
            mayor = tx if mayor is None else max(mayor, tx)
        return mayor
    except Exception:
        return None


def _bytes_grabadores():
    """
    {maquina: bytes enviados} de los grabadores. Varias fichas (record1b y
    record1n) son la misma maquina con dos carpetas: se pregunta una vez y se
    nombra por lo que tienen en comun ("record1").
    """
    from apps.pvr.models import StorageServer
    maquinas = {}
    for g in StorageServer.objects.filter(is_active=True).exclude(ssh_host=''):
        maquinas.setdefault((g.ssh_host, g.ssh_port, g.ssh_user), []).append(g.name)
    return {(os.path.commonprefix(nombres) or nombres[0]): _bytes_salida(*acceso)
            for acceso, nombres in maquinas.items()}


# Lo que el deco dice en cada latido que esta viendo (ver handle_watchdog).
VIENDO = ('videoclub', 'archivo', 'diferido', 'grabacion')
VIENDO_DURA = 180


def apuntar_viendo(device_id, que):
    from django.core.cache import cache
    try:
        if que in VIENDO:
            cache.set('viendo:%d' % device_id, que, VIENDO_DURA)
        else:
            cache.delete('viendo:%d' % device_id)
    except Exception:
        pass


def contar_viendo(ids):
    from django.core.cache import cache
    cuenta = dict.fromkeys(VIENDO, 0)
    try:
        for que in cache.get_many(['viendo:%d' % i for i in ids]).values():
            if que in cuenta:
                cuenta[que] += 1
    except Exception:
        pass
    return cuenta


def apuntar_muestra():
    """
    La llaman los latidos de los decos. Uno de cada 5 minutos coge el turno y
    lanza la muestra en un hilo: preguntar a los CDN tarda un segundo y el
    deco no tiene por que esperarlo.
    """
    from django.core.cache import cache
    try:
        if not cache.add('maquina:muestra:turno', 1, MUESTRA_CADA):
            return
        import threading
        threading.Thread(target=_tomar_muestra, daemon=True).start()
    except Exception:
        pass


def _tomar_muestra():
    from datetime import timedelta
    from django.core.cache import cache
    from django.db import connection
    from django.utils import timezone
    try:
        from apps.devices.models import Device
        from apps.channels.models import CdnServer
        ahora = time.time()
        encendidos = list(Device.objects.filter(
            last_seen__gte=timezone.now() - timedelta(minutes=5)).values_list('id', flat=True))
        decos = len(encendidos)
        viendo = contar_viendo(encendidos)
        total, parado = _tiempos_cpu()
        rx, tx = _bytes_red()
        cdns = {c.name: _bytes_salida_cdn(c)
                for c in CdnServer.objects.filter(is_active=True).order_by('name')}
        grabadores = _bytes_grabadores()
        antes = cache.get('maquina:contadores')
        cache.set('maquina:contadores', [ahora, total, parado, rx, tx, cdns, grabadores], None)
        cpu = sube = baja = None
        por_cdn = {}
        por_grabador = {}
        if antes and ahora > antes[0]:
            seg = ahora - antes[0]
            if total > antes[1] and tx >= antes[4] and rx >= antes[3]:
                cpu = round(100.0 * (1 - (parado - antes[2]) / (total - antes[1])))
                sube = round((tx - antes[4]) * 8 / seg / 1e6, 2)      # Mbit/s
                baja = round((rx - antes[3]) * 8 / seg / 1e6, 2)
            antes_cdn = antes[5] if len(antes) > 5 and isinstance(antes[5], dict) else {}
            for nombre, valor in cdns.items():
                previo = antes_cdn.get(nombre)
                if valor is not None and previo is not None and valor >= previo:
                    por_cdn[nombre] = round((valor - previo) * 8 / seg / 1e6, 1)
            antes_grab = antes[6] if len(antes) > 6 and isinstance(antes[6], dict) else {}
            for nombre, valor in grabadores.items():
                previo = antes_grab.get(nombre)
                if valor is not None and previo is not None and valor >= previo:
                    por_grabador[nombre] = round((valor - previo) * 8 / seg / 1e6, 1)
        historia = cache.get('maquina:historia') or []
        historia.append([int(ahora), decos, cpu, sube, baja, por_cdn, por_grabador, viendo])
        cache.set('maquina:historia', historia[-MUESTRAS:], None)
    except Exception:
        pass
    finally:
        try:
            connection.close()      # el hilo abre su propia conexion a la base
        except Exception:
            pass


def historia_maquina():
    from django.core.cache import cache
    try:
        desde = time.time() - MUESTRAS * MUESTRA_CADA
        return [m for m in (cache.get('maquina:historia') or []) if m[0] >= desde]
    except Exception:
        return []
