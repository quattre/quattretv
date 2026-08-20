#!/usr/bin/env python3
"""Cliente WebSocket minimo para hablar con el depurador de la LG y evaluar JS."""
import json, os, socket, base64, struct, sys, urllib.request

TV = sys.argv[1] if len(sys.argv) > 1 else '192.168.200.93:9998'
EXPR = sys.argv[2] if len(sys.argv) > 2 else '1+1'

paginas = json.load(urllib.request.urlopen('http://%s/json/list' % TV, timeout=15))
pagina = [p for p in paginas if p.get('type') == 'page'][0]
ruta = pagina['webSocketDebuggerUrl'].split(TV, 1)[1]

host, puerto = TV.split(':')
s = socket.create_connection((host, int(puerto)), timeout=20)
clave = base64.b64encode(os.urandom(16)).decode()
s.sendall(('GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
           'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (ruta, TV, clave)).encode())
cab = b''
while b'\r\n\r\n' not in cab:
    cab += s.recv(1)
assert b'101' in cab.split(b'\r\n')[0], cab[:80]

def enviar(texto):
    d = texto.encode()
    mask = os.urandom(4)
    ln = len(d)
    cabecera = b'\x81'
    if ln < 126:   cabecera += bytes([0x80 | ln])
    elif ln < 65536: cabecera += b'\xfe' + struct.pack('>H', ln)
    else: cabecera += b'\xff' + struct.pack('>Q', ln)
    s.sendall(cabecera + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(d)))

def recibir():
    def leer(n):
        b = b''
        while len(b) < n: b += s.recv(n - len(b))
        return b
    while True:
        c = leer(2)
        ln = c[1] & 127
        if ln == 126: ln = struct.unpack('>H', leer(2))[0]
        elif ln == 127: ln = struct.unpack('>Q', leer(8))[0]
        datos = leer(ln)
        if c[0] & 0x0f == 1:
            return datos.decode('utf-8', 'replace')

enviar(json.dumps({'id': 1, 'method': 'Runtime.evaluate',
                   'params': {'expression': EXPR, 'returnByValue': True}}))
for _ in range(40):
    m = json.loads(recibir())
    if m.get('id') == 1:
        r = m.get('result', {}).get('result', {})
        v = r.get('value', r.get('description', m.get('result')))
        print(json.dumps(v, indent=2, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        break
s.close()
