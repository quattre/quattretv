#!/usr/bin/env python3
"""
Saca las capturas del portal pintandolo en un navegador de escritorio.

Por que existe, habiendo ya capturas.py: aquel se engancha al depurador del
televisor, y el depurador de una LG solo funciona mientras dura la sesion de
Modo Desarrollador -- que caduca cada 50 horas y, al caducar, la television
borra la app. Cuando eso pasa no hay forma de sacar una captura, y las de la
tienda se quedan viejas justo cuando mas se cambia la interfaz.

El portal es una pagina web, asi que se puede pintar aqui a 1920x1080 con los
datos de verdad -- se entra con la MAC de un aparato dado de alta -- y sale la
misma interfaz. Lo unico que no sale es el video, porque en el televisor va en
un plano de hardware aparte; eso lo pone despues montar_video_en_capturas.py,
con un fotograma real bajado del CDN.

Se habla con Chrome por el mismo protocolo que con la television, y no por
Selenium, que en esta maquina no consigue arrancarlo ("DevToolsActivePort file
doesn't exist"). Ademas asi el codigo se parece al de capturas.py y no hay dos
formas distintas de hacer lo mismo.

Ojo con una cosa: aqui el navegador es Chrome moderno y en la television es
Chrome 53. Se parecen porque el portal esta escrito a proposito sin nada que el
53 no entienda -- sin 'gap', sin CSS Grid y sin variables -- pero si algun dia
se mete algo moderno, estas capturas dejarian de parecerse a lo que se ve en la
tele sin avisar.

    python3 lg_app/capturas_navegador.py <url-del-portal> <MAC> [carpeta]
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

PUERTO = 9333

# Cada paso: fichero, que ejecutar antes, cuanto esperar a que se pinte, y una
# descripcion. Se navega llamando a las funciones del portal en vez de mandar
# teclas: es lo mismo que hace el usuario y no depende de donde este el foco.
GUION = [
    ('01-canales',    'showChannels(); startPreview();',                     2.5, 'La lista de canales con la vista previa'),
    ('02-menu',       'openMenu();',                                         1.5, 'El menu principal'),
    ('03-categorias', 'openGenres();',                                       2.0, 'Los canales por categoria'),
    ('04-guia',       'showChannels(); currentChannel = 0; openGuide();',    3.5, 'La guia de programacion'),
    ('05-ficha',      'abrirFicha();',                                       2.0, 'La ficha completa del programa'),
    ('06-completa',   'showChannels(); currentChannel = 0; goFullscreen();', 3.5, 'Un canal a pantalla completa'),
    ('07-radio',      '''(function () {
        for (var i = 0; i < channels.length; i++) {
            if (channels[i].radio) {
                currentChannel = i; showChannels(); startPreview();
                return channels[i].number + " " + channels[i].name;
            }
        }
        return null;
    })()''',                                                                 3.0, 'Una emisora de radio'),
]


class Navegador:
    def __init__(self, puerto):
        base = 'http://localhost:%d' % puerto
        for _ in range(40):
            try:
                objetivos = json.load(urllib.request.urlopen(base + '/json', timeout=5))
                paginas = [o for o in objetivos if o.get('type') == 'page']
                if paginas:
                    self.ws = websocket.create_connection(
                        paginas[0]['webSocketDebuggerUrl'], timeout=60)
                    self.ws.settimeout(60)
                    self.n = 0
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise SystemExit('Chrome no ha abierto el puerto de depuracion')

    def manda(self, metodo, **params):
        self.n += 1
        self.ws.send(json.dumps({'id': self.n, 'method': metodo, 'params': params}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == self.n:
                return r.get('result', {})

    def js(self, expresion):
        r = self.manda('Runtime.evaluate', expression=expresion, returnByValue=True)
        if 'exceptionDetails' in r:
            return 'ERROR ' + str(r['exceptionDetails'].get('text'))[:90]
        return r.get('result', {}).get('value')

    def foto(self, destino):
        d = self.manda('Page.captureScreenshot', format='png')
        if not d.get('data'):
            return 0
        with open(destino, 'wb') as f:
            f.write(base64.b64decode(d['data']))
        return os.path.getsize(destino)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    url = sys.argv[1].rstrip('/') + '/'
    mac = sys.argv[2]
    carpeta = sys.argv[3] if len(sys.argv) > 3 else 'capturas'
    os.makedirs(carpeta, exist_ok=True)

    perfil = tempfile.mkdtemp(prefix='capturas-chrome-')
    chrome = subprocess.Popen([
        'google-chrome', '--headless', '--no-sandbox', '--disable-gpu',
        '--disable-dev-shm-usage', '--hide-scrollbars',
        '--window-size=1920,1080', '--force-device-scale-factor=1',
        # El portal deja el fondo transparente a proposito, para que asome el
        # plano de video del televisor. En un navegador eso saldria blanco.
        '--default-background-color=080b0d',
        '--user-data-dir=' + perfil,
        '--remote-debugging-port=%d' % PUERTO,
        # Desde Chrome 111 rechaza las conexiones al depurador que no vengan de
        # un origen autorizado, y las nuestras no traen ninguno.
        '--remote-allow-origins=*',
        'about:blank',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        nav = Navegador(PUERTO)
        nav.manda('Page.enable')
        nav.manda('Network.enable')
        # La MAC es la credencial del portal: sin ella devuelve el formulario de
        # acceso en vez de la aplicacion.
        dominio = url.split('/')[2]
        nav.manda('Network.setCookie', name='mac', value=mac, domain=dominio, path='/')
        nav.manda('Page.navigate', url=url)
        time.sleep(8)

        cargados = nav.js('typeof channels !== "undefined" ? channels.length : -1')
        if not isinstance(cargados, int) or cargados <= 0:
            raise SystemExit('El portal no ha cargado la lista de canales. '
                             '¿La MAC %s esta dada de alta?' % mac)
        print('Portal cargado: %d canales.' % cargados)

        for nombre, js, espera, descripcion in GUION:
            r = nav.js(js)
            if nombre == '07-radio':
                if not r:
                    print('  %-16s no hay ninguna emisora, se salta' % (nombre + '.png'))
                    continue
                print('  (emisora elegida: %s)' % r)
            time.sleep(espera)
            tam = nav.foto(os.path.join(carpeta, nombre + '.png'))
            print('  %-16s %-45s %6.1f KB' % (nombre + '.png', descripcion, tam / 1024))
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=10)
        except Exception:
            chrome.kill()
        shutil.rmtree(perfil, ignore_errors=True)


if __name__ == '__main__':
    main()
