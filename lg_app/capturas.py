#!/usr/bin/env python3
"""
Capturas de pantalla de la app, sacadas del televisor de verdad.

Para la ficha de la LG Content Store hacen falta capturas a 1920x1080 exactos.
Una foto de la pantalla no vale: sale el moire, el reflejo y el marco, y ademas
nunca da la resolucion pedida.

Esto se conecta al televisor por el protocolo de depuracion de webOS — el mismo
que usa el inspector web — y le pide a la app que se retrate. Es la aplicacion
real, corriendo en el aparato real, sin camara de por medio.

Antes de lanzarlo hay que abrir el puente con la television:

    ares-inspect -d lgtv -a com.quattre.tv

que responde con una direccion tipo http://localhost:45255. Esa es la que se le
pasa aqui.

    python3 lg_app/capturas.py http://localhost:45255 [carpeta]

Aviso conocido: en una television el video suele ir en un plano de hardware
aparte del navegador, asi que en las pantallas donde se esta viendo un canal es
posible que el hueco salga negro. La interfaz sale perfecta en todas.
"""
import base64
import json
import os
import sys
import time
import urllib.request

import websocket


class Tele:
    def __init__(self, base):
        objetivos = json.load(urllib.request.urlopen(base + '/json', timeout=10))
        paginas = [t for t in objetivos if t.get('type') == 'page']
        if not paginas:
            raise SystemExit('No hay ninguna pagina abierta en la television.')
        self.ws = websocket.create_connection(paginas[0]['webSocketDebuggerUrl'], timeout=20)
        self.n = 0
        self.enviar('Page.enable')
        self.enviar('Runtime.enable')

    def enviar(self, metodo, **params):
        self.n += 1
        self.ws.send(json.dumps({'id': self.n, 'method': metodo, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == self.n:
                if 'error' in msg:
                    raise SystemExit('%s: %s' % (metodo, msg['error']))
                return msg.get('result', {})

    def tecla(self, codigo, espera=1.2):
        """Una pulsacion del mando, tal y como la recibiria la app."""
        for tipo in ('rawKeyDown', 'keyUp'):
            self.enviar('Input.dispatchKeyEvent', type=tipo,
                        windowsVirtualKeyCode=codigo, nativeVirtualKeyCode=codigo)
        time.sleep(espera)

    def js(self, expresion):
        r = self.enviar('Runtime.evaluate', expression=expresion, returnByValue=True)
        return r.get('result', {}).get('value')

    def retrato(self, destino):
        r = self.enviar('Page.captureScreenshot', format='png')
        datos = base64.b64decode(r['data'])
        open(destino, 'wb').write(datos)
        return len(datos)


ARRIBA, ABAJO, IZQUIERDA, DERECHA, OK = 38, 40, 37, 39, 13

# Cada paso: nombre del fichero, que teclas pulsar antes, y una descripcion.
GUION = [
    ('01-canales',     [],                          'La lista de canales con la vista previa'),
    ('02-menu',        [IZQUIERDA],                 'El menu principal'),
    ('03-categorias',  [ABAJO, OK],                 'Los canales por categoria'),
    ('04-guia',        [IZQUIERDA, IZQUIERDA, DERECHA], 'La guia de programacion'),
    ('05-ficha',       [DERECHA],                   'La ficha completa del programa'),
    ('06-completa',    [IZQUIERDA, IZQUIERDA, OK],  'Un canal a pantalla completa'),
]


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    base = sys.argv[1].rstrip('/')
    carpeta = sys.argv[2] if len(sys.argv) > 2 else 'capturas'
    os.makedirs(carpeta, exist_ok=True)

    tele = Tele(base)
    print('Conectado a la television.')
    print('Pantalla actual segun la app:', tele.js('typeof view !== "undefined" ? view : "(sin cargar)"'))
    print()

    for nombre, teclas, descripcion in GUION:
        for t in teclas:
            tele.tecla(t)
        time.sleep(0.8)
        destino = os.path.join(carpeta, nombre + '.png')
        tam = tele.retrato(destino)
        print('  %-16s %-45s %6.1f KB' % (nombre + '.png', descripcion, tam / 1024))

    print()
    print('Guardadas en %s/' % carpeta)
    print('Repasa que ninguna salga con el hueco del video en negro; esas se')
    print('montan aparte con un fotograma real del canal.')


if __name__ == '__main__':
    main()
