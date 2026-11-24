#!/usr/bin/env python3
# Indice del archivo de siempre (dumpstream) para servirlo en HLS.
#
# El archivo de storage1 son piezas de una hora en MPEG-TS
# (records/archive/<carpeta>/AAAAMMDD-HH.mpg), lo mismo que llevan los trozos
# de un HLS. No hace falta convertir nada: basta con saber donde empieza cada
# rato de unos 10 s dentro de la pieza, y trozo.php entrega ese rato tal cual.
# El middleware monta con este indice la lista .m3u8 de cada programa.
#
# Cada trozo empieza en un fotograma clave, justo en la cabecera (PAT/PMT) que
# ffmpeg pone delante de cada uno, asi que se abre solo en cualquier aparato.
# No se lee el fichero entero: se salta ~10 s y se busca el siguiente
# fotograma clave (menos de 1 MB por trozo en vez de ~7 MB).
#
# La hora: el grabador escribe en directo, asi que la ultima escritura del
# fichero (mtime) es la hora de lo ultimo que tiene. Desde ahi hacia atras se
# cuenta con el reloj de la propia señal (PTS). Vale tambien para piezas
# cortadas (-temp) y para la de la hora en curso.
#
#   indexar_archivo.py            sin parar, cada minuto
#   indexar_archivo.py --pasada 300   una vuelta de 300 s como mucho (cron)
#   indexar_archivo.py --una 2    una pasada solo de esa carpeta y sale
#
# Hecho para el python3.5 de storage1 (sin f-strings).
import json
import os
import re
import sys
import time

ARCHIVO = '/mnt/storage1/quattretv/records/archive'
INDICE = '/mnt/storage1/quattretv/archive_hls/indice'
OBJETIVO = 10.0                 # segundos por trozo
LECTURA = 1 << 18               # se lee de 256 KB en 256 KB
MAX_BUSQUEDA = 16 << 20         # hasta 16 MB buscando un fotograma clave
HORAS = 170                     # piezas de la ultima semana (y un poco)
ABIERTA = 180                   # segundos sin escribir para darla por cerrada
VUELTA = 2 ** 33 / 90000.0      # el PTS da la vuelta cada ~26,5 h
PIEZA = re.compile(r'^(\d{8})-(\d{2})\.mpg(-temp)?$')
TS = 188


def log(texto):
    sys.stdout.write(time.strftime('%H:%M:%S ') + texto + '\n')
    sys.stdout.flush()


def dif(a, b):
    """Segundos de PTS de a a b, con la vuelta."""
    d = (b - a) % VUELTA
    return d - VUELTA if d > VUELTA / 2 else d


def sincronizar(d):
    """Primer byte de d donde empiezan paquetes TS seguidos."""
    i = d.find(b'\x47')
    while 0 <= i < len(d) - 2 * TS:
        if d[i + TS] == 0x47 and d[i + 2 * TS] == 0x47:
            return i
        i = d.find(b'\x47', i + 1)
    return -1


def carga(p):
    """Donde empieza la carga util de un paquete con PUSI, o None."""
    af = (p[3] >> 4) & 3
    if af == 2:
        return None
    return 4 + (1 + p[4] if af == 3 else 0)


def pts_pes(e):
    if len(e) >= 14 and e[:3] == b'\x00\x00\x01' and e[7] & 0x80:
        b = e[9:14]
        return (((b[0] >> 1) & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | b[4] >> 1) / 90000.0
    return None


def pid_video(f):
    """PID del video, de la PAT y la PMT del principio de la pieza."""
    f.seek(0)
    d = f.read(4 << 20)
    i = sincronizar(d)
    if i < 0:
        return None
    pmts = set()
    for pos in range(i, len(d) - TS + 1, TS):
        p = d[pos:pos + TS]
        if p[0] != 0x47 or not p[1] & 0x40:
            continue
        pid = ((p[1] & 0x1f) << 8) | p[2]
        o = carga(p)
        if o is None or o >= TS:
            continue
        s = p[o + 1 + p[o]:]
        if len(s) < 12:
            continue
        n = ((s[1] & 0xf) << 8) | s[2]
        if pid == 0:
            for j in range(8, min(3 + n - 4, len(s) - 4), 4):
                if (s[j] << 8 | s[j + 1]) != 0:
                    pmts.add(((s[j + 2] & 0x1f) << 8) | s[j + 3])
        elif pid in pmts:
            j = 12 + (((s[10] & 0xf) << 8) | s[11])
            while j + 5 <= min(3 + n - 4, len(s)):
                tipo = s[j]
                ep = ((s[j + 1] & 0x1f) << 8) | s[j + 2]
                if tipo in (0x01, 0x02, 0x1b, 0x24):
                    return ep
                j += 5 + (((s[j + 3] & 0xf) << 8) | s[j + 4])
    return None


def clave_desde(f, desde, vid, tope):
    """
    (posicion, pts) del primer fotograma clave a partir de `desde` y antes de
    `tope`. La posicion es la de la PAT que va delante si esta pegada (ffmpeg
    la pone dos paquetes antes), para que el trozo se abra solo.
    """
    pos = desde
    leido = 0
    while pos < tope and leido < MAX_BUSQUEDA:
        f.seek(pos)
        d = f.read(min(LECTURA, tope - pos))
        if len(d) < 3 * TS:
            return None
        i = sincronizar(d)
        if i < 0:
            return None
        q = i
        while q + TS <= len(d):
            p = d[q:q + TS]
            if p[0] != 0x47:
                break
            if (((p[1] & 0x1f) << 8) | p[2]) == vid and p[1] & 0x40 \
                    and (p[3] >> 4) & 3 == 3 and p[4] > 0 and p[5] & 0x40:
                t = pts_pes(p[carga(p):])
                if t is not None:
                    inicio = pos + q
                    for atras in (1, 2, 3):
                        r = q - atras * TS
                        if r >= 0 and d[r] == 0x47 and (((d[r + 1] & 0x1f) << 8) | d[r + 2]) == 0:
                            inicio = pos + r
                            break
                    return inicio, t
            q += TS
        avance = max(q, TS)
        pos += avance
        leido += avance
    return None


def ultimo_pts(f, tam, vid):
    """PTS de video mas nuevo de la pieza (de sus ultimos MB)."""
    for tramo in (2 << 20, 8 << 20):
        f.seek(max(0, tam - tramo))
        d = f.read(tramo)
        i = sincronizar(d)
        mejor = None
        if i >= 0:
            for q in range(i, len(d) - TS + 1, TS):
                p = d[q:q + TS]
                if p[0] != 0x47:
                    break
                if ((p[1] & 0x1f) << 8 | p[2]) == vid and p[1] & 0x40:
                    o = carga(p)
                    t = pts_pes(p[o:]) if o is not None else None
                    if t is not None and (mejor is None or dif(mejor, t) > 0):
                        mejor = t
        if mejor is not None:
            return mejor
    return None


def puntos_de(f, tam, vid, puntos):
    """Sigue buscando fotogramas clave cada ~10 s desde el ultimo conocido."""
    ritmo = None                    # bytes por segundo de la señal
    if len(puntos) >= 2:
        (p0, t0), (p1, t1) = puntos[-2], puntos[-1]
        if 0 < dif(t0, t1) < 60:
            ritmo = (p1 - p0) / dif(t0, t1)
    if not puntos:
        c = clave_desde(f, 0, vid, tam)
        if not c:
            return puntos
        puntos.append(list(c))
    tope = tam - (1 << 20)          # lo ultimo puede estar a medio escribir
    while True:
        pos, t = puntos[-1]
        salto = int(ritmo * (OBJETIVO - 0.5)) if ritmo else (1 << 20)
        c = clave_desde(f, pos + max(salto, 4 * TS), vid, tope)
        if not c:
            return puntos
        d = dif(t, c[1])
        if 0 < d < 60:
            ritmo = (c[0] - pos) / d
        puntos.append(list(c))


def trozos_de(puntos, tam, pts_fin, fin_epoch, cerrada):
    """
    [[inicio UTC, posicion, longitud, duracion, pts], ...]. Las duraciones salen del
    PTS; si la señal tuvo un corte (PTS que salta) se estima por los bytes.
    """
    if not puntos:
        return []
    filas = []
    for (p0, t0), (p1, t1) in zip(puntos, puntos[1:]):
        filas.append([p0, p1 - p0, dif(t0, t1), t0])
    if cerrada:
        p0, t0 = puntos[-1]
        filas.append([p0, tam - p0, max(0.04, dif(t0, pts_fin) + 0.04), t0])
    buenos = [r for r in filas if 0 < r[2] < 60]
    bps = (sum(r[1] for r in buenos) / sum(r[2] for r in buenos)) if buenos else 600000.0
    for r in filas:
        if not 0 < r[2] < 60:
            r[2] = r[1] / bps
    # Hacia atras desde la hora de lo ultimo que se escribio.
    if cerrada:
        fin = fin_epoch
    else:
        fin = fin_epoch - max(0.0, dif(puntos[-1][1], pts_fin))
    salida = []
    for p, n, d, t in reversed(filas):
        fin -= d
        salida.append([round(fin, 3), p, n, round(d, 3), round(t, 3)])
    salida.reverse()
    return salida


def hora_de(nombre):
    m = PIEZA.match(nombre)
    if not m:
        return None
    return time.mktime(time.strptime(m.group(1) + m.group(2), '%Y%m%d%H'))


def indexar(carpeta, nombre):
    ruta = os.path.join(ARCHIVO, carpeta, nombre)
    destino_dir = os.path.join(INDICE, carpeta)
    destino = os.path.join(destino_dir, nombre + '.json')
    try:
        st = os.stat(ruta)
    except OSError:
        return False
    # Ya indexada despues de cerrarse: ni se abre el indice (son miles).
    try:
        if os.stat(destino).st_mtime > st.st_mtime + ABIERTA:
            return False
    except OSError:
        pass
    previo = None
    try:
        with open(destino) as g:
            previo = json.load(g)
    except (IOError, OSError, ValueError):
        pass
    if previo and previo.get('t') == st.st_mtime and previo.get('s') == st.st_size and previo.get('cerrada'):
        return False
    cerrada = time.time() - st.st_mtime > ABIERTA
    # Si el fichero es el mismo y solo ha crecido, se sigue donde se dejo.
    puntos = []
    if previo and previo.get('s', 0) <= st.st_size and previo.get('puntos') and previo.get('i') == st.st_ino:
        puntos = previo['puntos']
    with open(ruta, 'rb') as f:
        vid = (previo or {}).get('vid') if puntos else None
        vid = vid or pid_video(f)
        if vid is None:
            return False
        puntos = puntos_de(f, st.st_size, vid, puntos)
        pts_fin = ultimo_pts(f, st.st_size, vid)
    if not puntos or pts_fin is None:
        return False
    # Una pieza que se rehizo despues (la compactacion de dumpstream) tiene la
    # fecha de cuando se rehizo: entonces se toma el final de su hora.
    fin = st.st_mtime
    inicio_hora = hora_de(nombre)
    if inicio_hora is not None and fin > inicio_hora + 3600 + 300:
        fin = inicio_hora + 3600
    datos = {
        't': st.st_mtime, 's': st.st_size, 'i': st.st_ino, 'vid': vid, 'cerrada': cerrada,
        'puntos': puntos,
        'trozos': trozos_de(puntos, st.st_size, pts_fin, fin, cerrada),
    }
    if not os.path.isdir(destino_dir):
        os.makedirs(destino_dir)
    tmp = destino + '.tmp'
    with open(tmp, 'w') as g:
        json.dump(datos, g, separators=(',', ':'))
    os.rename(tmp, destino)
    return True


def limpiar(carpeta, nombres):
    d = os.path.join(INDICE, carpeta)
    if not os.path.isdir(d):
        return
    for n in os.listdir(d):
        if n.endswith('.json') and n[:-5] not in nombres:
            try:
                os.remove(os.path.join(d, n))
            except OSError:
                pass


def pasada(solo=None, presupuesto=None):
    """Una vuelta: primero lo mas nuevo de todos los canales, luego hacia atras."""
    empiezo = time.time()
    limite = empiezo - HORAS * 3600
    piezas = []
    carpetas = [solo] if solo else [c for c in os.listdir(ARCHIVO) if c.isdigit()]
    for c in carpetas:
        try:
            nombres = [n for n in os.listdir(os.path.join(ARCHIVO, c)) if PIEZA.match(n)]
        except OSError:
            continue
        limpiar(c, set(nombres))
        for n in nombres:
            h = hora_de(n)
            if h and h >= limite:
                piezas.append((h, c, n))
    piezas.sort(reverse=True)
    hechas = 0
    for h, c, n in piezas:
        if presupuesto and time.time() - empiezo > presupuesto:
            break
        try:
            if indexar(c, n):
                hechas += 1
        except Exception as e:
            log('%s/%s: %s' % (c, n, e))
    return hechas


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--una':
        log('%d piezas indexadas' % pasada(sys.argv[2]))
        return
    if len(sys.argv) > 2 and sys.argv[1] == '--pasada':
        # Desde el cron de cada minuto (con flock): una vuelta de como mucho
        # esos segundos.
        empiezo = time.time()
        hechas = pasada(presupuesto=int(sys.argv[2]))
        if hechas:
            log('%d piezas indexadas en %d s' % (hechas, time.time() - empiezo))
        return
    log('indexando %s en %s' % (ARCHIVO, INDICE))
    while True:
        empiezo = time.time()
        hechas = pasada(presupuesto=600)
        if hechas:
            log('%d piezas indexadas en %d s' % (hechas, time.time() - empiezo))
        time.sleep(max(5, 60 - (time.time() - empiezo)))


if __name__ == '__main__':
    main()
