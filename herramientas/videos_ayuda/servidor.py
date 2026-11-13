# Sirve el portal en local (127.0.0.1:8765) con los datos reales de iptv2 (cuenta de pruebas),
# para grabar las guias sin tocar nada. Uso: GUIAS_MAC=... python3 servidor.py <raiz del repositorio>
import http.server, re, sys, urllib.request, os
RAIZ = sys.argv[1]
# Las MAC de las cuentas de pruebas son su credencial: no van en el repositorio.
MAC = os.environ['GUIAS_MAC']                              # la cuenta con la que se ve la tele
MAC_ARCHIVO = os.environ.get('GUIAS_MAC_ARCHIVO', MAC)    # la que tiene archivo (videoclub 7 dias)
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        ruta, _, q = self.path.partition('?')
        if ruta.startswith('/static/'):
            f = os.path.join(RAIZ, 'apps/stalker_api/static', ruta[len('/static/'):])
            if not os.path.isfile(f): return self.send_error(404)
            tipo = {'.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.woff': 'font/woff'}.get(os.path.splitext(f)[1], 'application/octet-stream')
            datos = open(f, 'rb').read()
        elif ruta.startswith('/stb') and q:
            if 'type=ayuda' in q:
                import json as J
                if 'action=inicio' in q: av_vacio = True
                av = [{'id': 1, 'titulo': 'Nuevo: Videoclub 7 dias', 'texto': 'Pulsa la tecla amarilla del mando para ver todo lo emitido en los ultimos 7 dias: peliculas, series, documentales y programas.\n\nElige con las flechas y pulsa OK. Si dejas algo a medias, lo encontraras en Seguir viendo.\n\nLinea 4\nLinea 5\nLinea 6\nLinea 7\nLinea 8\nLinea 9\nLinea 10\nLinea 11\nLinea 12\nLinea 13', 'img': '/static/stb/fondo.jpg', 'video': 'https://iptv2.quattre.com/quattretv/stb/?type=ayuda&action=video&id=2'},
                      {'id': 2, 'titulo': 'Como grabar un programa', 'texto': 'En la guia, elige el programa y pulsa la tecla roja.', 'img': '', 'video': ''}]
                datos = J.dumps({'js': {'data': [] if 'action=inicio' in q else av, 'result': True}}).encode()
            elif 'action=set_fav' in q:
                datos = b'{"js": {"result": true}}'   # finge que se guarda, sin tocar la cuenta
            elif 'action=set_progress' in q or 'action=create_link' in q:
                datos = b'{"js": {}}'
            else:
                mac = MAC_ARCHIVO if 'type=tv_archive' in q else MAC
                r = urllib.request.Request('https://iptv2.quattre.com/quattretv/stb/?' + q, headers={'Cookie': 'mac=' + mac})
                datos = urllib.request.urlopen(r, timeout=30).read()
                if 'action=get_modules' in q: datos = datos.replace(b'"settings"', b'"settings", "semana", "ayuda", "lateral"')
            tipo = 'application/json'
        elif ruta.startswith('/stb'):
            t = open(os.path.join(RAIZ, 'templates/stb/', 'loader.html' if 'login' in ruta else 'portal.html')).read()
            t = t.replace('{% load static %}', '')
            t = re.sub(r"\{% static '([^']+)' %\}", r"/static/\1", t)
            t = re.sub(r"\{\{[^}]*\}\}|\{%[^%]*%\}", "", t)
            datos = t.encode(); tipo = 'text/html; charset=utf-8'
        else:
            return self.send_error(404)
        self.send_response(200); self.send_header('Content-Type', tipo); self.end_headers(); self.wfile.write(datos)
http.server.ThreadingHTTPServer(('127.0.0.1', 8765), H).serve_forever()
