#!/usr/bin/env python3
# Archivo de un canal: guarda en disco los trozos del HLS del directo del CDN.
#
# No recodifica ni recorta nada: son los mismos trozos que ve el cliente en
# directo, asi que se reproducen igual en todas partes. Cada trozo se guarda
# con la hora UTC de su inicio (AAAAMMDD-HHMMSS.ts), sacada del nombre que le
# pone el CDN (segment_2026-11-23_17-34-22.ts, hora de Madrid). De esos nombres
# monta el middleware la lista .m3u8 de cada programa.
#
#   recoger_hls.py <url index.m3u8 del CDN> <carpeta>
#
# Hecho para el python3.5 de storage1 (sin f-strings).
import os
import re
import sys
import time
import urllib.parse
import urllib.request

PAUSA = 4            # segundos entre lecturas de la lista (los trozos son de 10 s)
RECORDAR = 60        # nombres del CDN ya guardados que se recuerdan
HORA_CDN = re.compile(r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})')


def log(texto):
    sys.stdout.write(time.strftime('%H:%M:%S ') + texto + '\n')
    sys.stdout.flush()


def nombre_utc(nombre_cdn):
    """'segment_2026-11-23_17-34-22.ts' (hora local, TZ del proceso) -> '20261123-163422.ts'."""
    m = HORA_CDN.search(nombre_cdn)
    if m:
        local = tuple(int(x) for x in m.groups()) + (0, 0, -1)
        instante = time.mktime(local)
    else:
        instante = time.time()
    return time.strftime('%Y%m%d-%H%M%S', time.gmtime(instante)) + '.ts'


def bajar(url, destino):
    parte = os.path.join(os.path.dirname(destino), '.' + os.path.basename(destino) + '.parte')
    try:
        with urllib.request.urlopen(url, timeout=20) as r, open(parte, 'wb') as f:
            while True:
                bloque = r.read(1 << 16)
                if not bloque:
                    break
                f.write(bloque)
        if os.path.getsize(parte) == 0:
            raise IOError('trozo vacio')
        os.rename(parte, destino)
        return True
    except Exception as e:
        log('no se pudo bajar %s: %s' % (url, e))
        try:
            os.remove(parte)
        except OSError:
            pass
        return False


def main():
    origen, carpeta = sys.argv[1], sys.argv[2]
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    vistos = []
    log('archivando %s en %s' % (origen, carpeta))
    while True:
        try:
            lista = urllib.request.urlopen(origen, timeout=10).read().decode('utf-8', 'replace')
        except Exception as e:
            log('la lista no contesta: %s' % e)
            time.sleep(PAUSA)
            continue
        for linea in lista.splitlines():
            linea = linea.strip()
            if not linea or linea.startswith('#') or linea in vistos:
                continue
            destino = os.path.join(carpeta, nombre_utc(linea))
            if os.path.exists(destino) or bajar(urllib.parse.urljoin(origen, linea), destino):
                vistos.append(linea)
                vistos = vistos[-RECORDAR:]
        time.sleep(PAUSA)


if __name__ == '__main__':
    main()
