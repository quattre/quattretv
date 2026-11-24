#!/usr/bin/env python3
# Indice de las grabaciones de los clientes en record1, para servirlas en HLS.
#
# Lo mismo que indexar_archivo.py hace con el archivo de storage1 (y con sus
# mismas funciones): cada grabacion es un MPEG-TS entero, y se apunta donde
# empieza cada rato de ~10 s en un fotograma clave. grabacion.php monta con
# esto la lista .m3u8 y trozo.php entrega cada rato tal cual. Asi las abre
# cualquier aparato que sepa HLS (la app de Android sin actualizar, LG,
# Samsung...), no solo el deco. La grabacion no se toca: solo se lee.
#
#   indexar_grabaciones.py --pasada 290       una vuelta (cron, con flock)
#   indexar_grabaciones.py --una nuevas F     solo esa grabacion (grabacion.php
#                                             la pide si aun no tiene indice)
#
# Hecho para el python3.5 de record1 (sin f-strings).
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indexar_archivo as ix  # noqa: E402

# Las dos carpetas que sirve Apache en quattretv_grab/ (sus enlaces).
CARPETAS = {
    'nuevas': '/mnt/record1/quattretv/records_quattretv',
    'ministra': '/mnt/record1/quattretv/records',
}
INDICE = '/mnt/record1/quattretv/grab_hls/indice'
GRABACION = re.compile(r'^\d+_\d{14}\.(mpg|ts)$')
ABIERTA = 180       # segundos sin escribir para darla por terminada


def indexar(d, nombre):
    ruta = os.path.join(CARPETAS[d], nombre)
    destino_dir = os.path.join(INDICE, d)
    destino = os.path.join(destino_dir, nombre + '.json')
    st = os.stat(ruta)
    if time.time() - st.st_mtime < ABIERTA:
        return False            # todavia grabando
    try:
        if os.stat(destino).st_mtime > st.st_mtime:
            return False        # ya hecho
    except OSError:
        pass
    with open(ruta, 'rb') as f:
        vid = ix.pid_video(f)
        if vid is None:
            return False
        puntos = ix.puntos_de(f, st.st_size, vid, [])
        pts_fin = ix.ultimo_pts(f, st.st_size, vid)
    if not puntos or pts_fin is None:
        return False
    trozos = ix.trozos_de(puntos, st.st_size, pts_fin, 0.0, True)
    cero = trozos[0][0]
    # Segundos desde el principio de la grabacion, no hora del reloj.
    trozos = [[round(t[0] - cero, 3)] + t[1:] for t in trozos]
    if not os.path.isdir(destino_dir):
        os.makedirs(destino_dir)
    tmp = destino + '.%d.tmp' % os.getpid()
    with open(tmp, 'w') as g:
        json.dump({'s': st.st_size, 'trozos': trozos}, g, separators=(',', ':'))
    os.chmod(tmp, 0o666)
    os.rename(tmp, destino)
    return True


def limpiar(d, nombres):
    carpeta = os.path.join(INDICE, d)
    if not os.path.isdir(carpeta):
        return
    for n in os.listdir(carpeta):
        if n.endswith('.json') and n[:-5] not in nombres:
            try:
                os.remove(os.path.join(carpeta, n))
            except OSError:
                pass


def pasada(presupuesto):
    empiezo = time.time()
    todas = []
    for d, carpeta in CARPETAS.items():
        try:
            nombres = [n for n in os.listdir(carpeta) if GRABACION.match(n)]
        except OSError:
            continue
        limpiar(d, set(nombres))
        for n in nombres:
            try:
                todas.append((os.stat(os.path.join(carpeta, n)).st_mtime, d, n))
            except OSError:
                pass
    todas.sort(reverse=True)    # las mas nuevas primero: son las que se ven
    hechas = 0
    for _, d, n in todas:
        if time.time() - empiezo > presupuesto:
            break
        try:
            if indexar(d, n):
                hechas += 1
        except Exception as e:
            ix.log('%s/%s: %s' % (d, n, e))
    return hechas


def main():
    if len(sys.argv) > 3 and sys.argv[1] == '--una':
        d, n = sys.argv[2], sys.argv[3]
        if d not in CARPETAS or not GRABACION.match(n):
            sys.exit(2)
        indexar(d, n)
        return
    if len(sys.argv) > 2 and sys.argv[1] == '--pasada':
        empiezo = time.time()
        hechas = pasada(int(sys.argv[2]))
        if hechas:
            ix.log('%d grabaciones indexadas en %d s' % (hechas, time.time() - empiezo))
        return
    print(__doc__ if __doc__ else 'uso: --pasada N | --una carpeta fichero')


if __name__ == '__main__':
    main()
