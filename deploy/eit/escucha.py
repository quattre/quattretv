"""
Escuchador de solo lectura de la EIT (ahora / siguiente) de los multicast
de este CDN: la hora de verdad a la que empieza cada programa.

Apunta cada cambio en cambios.log y manda los de "ahora" a iptv2, que los
usa para que el archivo empiece donde empieza el programa (apps/epg/eit.py).
No toca ffmpeg ni nginx: solo se une a los grupos que ffmpeg ya recibe.

Va en /home/quattre/eit/ con envio.conf al lado (dos lineas: la URL de
recibir_eit y la clave EIT_TOKEN). Sin envio.conf solo apunta. Lo arranca y
lo vigila el cron del usuario quattre (ver deploy/eit/README).
"""
import datetime, glob, json, os, re, select, socket, struct, sys, threading, time
import urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = open(os.path.join(DIR, 'cambios.log'), 'a', buffering=1)

# ---------- Envio a iptv2 ----------
PENDIENTES, CERROJO = [], threading.Lock()
try:
    URL, CLAVE = [l.strip() for l in open(os.path.join(DIR, 'envio.conf')).read().split()[:2]]
except (OSError, ValueError):
    URL = CLAVE = None

def enviar():
    while True:
        time.sleep(15)
        with CERROJO:
            lote = PENDIENTES[:500]
        if not lote or not URL:
            continue
        try:
            peticion = urllib.request.Request(URL, data=json.dumps({'cambios': lote}).encode(),
                                              headers={'Content-Type': 'application/json',
                                                       'X-EIT-Token': CLAVE})
            urllib.request.urlopen(peticion, timeout=20).read()
            with CERROJO:
                del PENDIENTES[:len(lote)]
        except Exception as error:
            print('envio:', error, flush=True)
            with CERROJO:
                # Si iptv2 no contesta en mucho rato, lo viejo ya no sirve.
                del PENDIENTES[:max(0, len(PENDIENTES) - 5000)]

threading.Thread(target=enviar, daemon=True).start()
# PID 0x12 (EIT) y PID 0 (PAT, para saber que servicio es el nuestro).
PID_EIT = re.compile(rb'\x47[\x00\x20\x40\x60\x80\xa0\xc0\xe0][\x12\x00]')
CANALES = open(os.path.join(DIR, 'canales.tsv'), 'a', buffering=1)

def bcd(b): return (b >> 4) * 10 + (b & 15)

def mjd(m, h, mi, s):
    y = int((m - 15078.2) / 365.25); mo = int((m - 14956.1 - int(y * 365.25)) / 30.6001)
    d = m - 14956 - int(y * 365.25) - int(mo * 30.6001); k = 1 if mo in (14, 15) else 0
    return datetime.datetime(1900 + y + k, mo - 1 - k * 12, d, bcd(h), bcd(mi), bcd(s))

canales = {}
for f in sorted(glob.glob('/home/quattre/canales/*')):
    try:
        m = re.search(r'SRC=udp://@?([\d.]+):(\d+)', open(f).read())
    except Exception:
        continue
    if not m or (m.group(1), int(m.group(2))) in [(c['ip'], c['port']) for c in canales.values()]:
        continue
    ip, port = m.group(1), int(m.group(2))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((ip, port))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                     struct.pack('4sl', socket.inet_aton(ip), socket.INADDR_ANY))
    except OSError as e:
        print('no', f, e, flush=True); s.close(); continue
    s.setblocking(False)
    canales[s.fileno()] = {'s': s, 'nombre': os.path.basename(f), 'ip': ip, 'port': port, 'buf': b'', 'visto': {}, 'sids': None}
print(len(canales), 'canales', flush=True)

def ahora():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def pat(c, p):
    if c['sids'] is not None or not (p[1] & 0x40) or (p[3] >> 4) & 3 != 1:
        return
    sec = p[5 + p[4]:]
    if sec[:1] != b'\x00':
        return
    L = ((sec[1] & 0x0f) << 8 | sec[2]) + 3
    sids = []
    for i in range(8, min(L, len(sec)) - 4, 4):
        n = sec[i] << 8 | sec[i+1]
        if n:
            sids.append(n)
    if sids:
        c['sids'] = set(sids)
        CANALES.write('\t'.join([ahora(), c['nombre'], c['ip'], str(c['port']),
                                  ','.join(map(str, sids))]) + '\n')

def seccion(c, sec):
    if sec[0] != 0x4e or len(sec) < 18:
        return
    sid, secn = sec[3] << 8 | sec[4], sec[6]
    # Hay multicast que traen la EIT de todo el paquete del que salen.
    if not c['sids'] or sid not in c['sids']:
        return
    j, L = 14, len(sec)
    while j + 12 <= L - 4:
        try:
            ini = mjd(sec[j+2] << 8 | sec[j+3], sec[j+4], sec[j+5], sec[j+6])
        except ValueError:
            return
        dur = bcd(sec[j+7]) * 3600 + bcd(sec[j+8]) * 60 + bcd(sec[j+9])
        rs = sec[j+10] >> 5; dl = (sec[j+10] & 15) << 8 | sec[j+11]
        nombre, k = '', j + 12
        while k + 2 <= j + 12 + dl and k + 2 <= L:
            if sec[k] == 0x4d and k + 6 <= L:
                nl = sec[k+5]
                t = sec[k+6:k+6+nl]
                if t[:1] and t[0] < 0x20: t = t[1:]
                nombre = t.decode('latin-1', 'replace').strip()
            k += 2 + sec[k+1]
        clave = (sid, secn)
        valor = (ini, dur, rs, nombre)
        if c['visto'].get(clave) != valor:
            # El primero de cada canal es como estaba al arrancar, no un cambio.
            if clave in c['visto'] and secn == 0:
                with CERROJO:
                    PENDIENTES.append({'canal': c['nombre'], 'tipo': 'AHORA', 'nombre': nombre,
                                       'inicio': ini.strftime('%Y-%m-%d %H:%M:%S'), 'visto': ahora()})
            c['visto'][clave] = valor
            LOG.write('\t'.join([ahora(), c['nombre'],
                                 str(sid), 'AHORA' if secn == 0 else 'LUEGO',
                                 ini.strftime('%Y-%m-%d %H:%M:%S'), str(dur), str(rs), nombre]) + '\n')
        j += 12 + dl

def paquete(c, p):
    af = (p[3] >> 4) & 3
    o = 4 + (1 + p[4] if af in (2, 3) else 0)
    if af == 2 or o >= 188:
        return
    pay = p[o:]
    if p[1] & 0x40:
        c['buf'] = pay[1 + pay[0]:]
    elif c['buf']:
        c['buf'] += pay
    else:
        return
    b = c['buf']
    while len(b) >= 3 and b[0] != 0xff:
        L = ((b[1] & 0x0f) << 8 | b[2]) + 3
        if len(b) < L:
            break
        seccion(c, b[:L]); b = b[L:]
    c['buf'] = b if len(b) < 4096 else b''

fin = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 86400)
fds = list(canales)
while time.time() < fin:
    listos, _, _ = select.select(fds, [], [], 1)
    for fd in listos:
        c = canales[fd]
        for _ in range(64):
            try:
                d = c['s'].recv(2048)
            except BlockingIOError:
                break
            for m in PID_EIT.finditer(d):
                i = m.start()
                if (i - (len(d) % 188)) % 188 == 0 and i + 188 <= len(d):
                    if d[i+2] == 0:
                        pat(c, d[i:i+188])
                    else:
                        paquete(c, d[i:i+188])
