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
# El canal que sale en las capturas. Se elige a proposito uno de imagen neutra
# y luminosa: las capturas de la tienda se quedan puestas meses y en un canal de
# noticias sale el titular del dia -- la primera tanda salio con un titular
# politico y un telefono en pantalla. El deporte y los documentales envejecen
# mejor. Es un numero de canal, no una posicion en la lista.
CANAL_ESCAPARATE = 37       # Teledeporte

GUION = [
    ('01-canales',    'currentChannel = __c; showChannels(); startPreview();', 2.5, 'La lista de canales con la vista previa'),
    ('02-menu',       'openMenu();',                                         1.5, 'El menu principal'),
    ('03-categorias', 'openGenres();',                                       2.0, 'Los canales por categoria'),
    ('04-guia',       'showChannels(); currentChannel = __c; openGuide();',  3.5, 'La guia de programacion'),
    ('05-ficha',      'abrirFicha();',                                       2.0, 'La ficha completa del programa'),
    # A pantalla completa se enseña ademas la barra de informacion: sin ella la
    # captura es el canal a secas y no se ve nada de la aplicacion.
    ('06-completa',   'showChannels(); currentChannel = __c; goFullscreen();'
                      ' mostrarOsd(channels[__c]);',                         3.5, 'Un canal a pantalla completa'),
    # Hay que SALIR de pantalla completa antes de la radio. Se venia de la
    # captura anterior, y showChannels() cambia la vista pero deja isFullscreen
    # a true y la capa de graficos apagada: la captura salia identica a la 06,
    # byte a byte, y nadie lo noto porque las dos parecian correctas por
    # separado.
    ('07-radio',      '''(function () {
        showMenu();
        for (var i = 0; i < channels.length; i++) {
            if (channels[i].radio) {
                currentChannel = i; showChannels(); startPreview();
                return channels[i].number + " " + channels[i].name;
            }
        }
        return null;
    })()''',                                                                 3.5, 'Una emisora de radio'),
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
        # Aqui no hay video: un Chrome de escritorio no reproduce el HLS de los
        # canales. El portal, cuando no consigue arrancar la imagen, escribe en
        # su lugar por que ha fallado y el estado del reproductor -- que es justo
        # lo que se quiere en un televisor y justo lo que no puede salir en una
        # captura para la tienda. Se vacia antes de disparar; el hueco lo rellena
        # despues montar_video_en_capturas.py con un fotograma de verdad.
        # Y se quita el aviso emergente: aqui salta "este contenido no se puede
        # reproducir en este dispositivo" en cuanto se toca una emisora de radio,
        # porque Chrome tampoco reproduce ese flujo. En el televisor no aparece.
        self.js('''(function(){
            var c = document.getElementById("preview");
            if (c && /No se pudo iniciar la imagen/.test(c.innerHTML)) c.innerHTML = "";
            var t = document.getElementById("toast");
            if (t) t.style.display = "none";
            return 1;
        })()''')
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
        # Aqui iba '--default-background-color', para que el fondo transparente
        # del portal no saliera blanco. No se puede: Chrome lo cuenta como
        # "orden de headless" y no admite ordenes de headless a la vez que el
        # depurador -- se niega a arrancar con un escueto "Headless commands are
        # not compatible with remote debugging" y ni siquiera abre el puerto.
        # Por eso este script no funcionaba en ninguna maquina con Chrome
        # moderno, y parecia cosa de esta. El color se pone mas abajo por el
        # propio protocolo, que hace lo mismo y si convive con el depurador.
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
        # El fondo que antes se pedia por linea de comandos, y en NEGRO PURO.
        #
        # El parametro original pedia #080B0D, el gris muy oscuro de la
        # aplicacion, y eso rompe el montaje del video: montar_video_en_capturas
        # busca el hueco por el negro, y 08 ya no es negro. Con aquel color, la
        # captura de pantalla completa no se reconocia como tal y se le metia el
        # video en el recuadro pequeño, como si fuera la vista previa.
        #
        # Negro es ademas lo que se ve de verdad: en el televisor esa zona es el
        # plano de video, y en una captura sale negra.
        nav.manda('Emulation.setDefaultBackgroundColorOverride',
                  color={'r': 0, 'g': 0, 'b': 0, 'a': 1})
        # La MAC es la credencial del portal: sin ella devuelve el formulario de
        # acceso en vez de la aplicacion.
        dominio = url.split('/')[2]
        nav.manda('Network.setCookie', name='mac', value=mac, domain=dominio, path='/')
        nav.manda('Page.navigate', url=url)
        time.sleep(8)

        # __c es la posicion del canal escaparate dentro de la lista, que no es
        # su numero: la lista va filtrada por lo que ve cada aparato.
        nav.js('''window.__c = (function () {
            for (var i = 0; i < channels.length; i++) {
                if (String(channels[i].number) === "%d") return i;
            }
            return 0;
        })()''' % CANAL_ESCAPARATE)

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
