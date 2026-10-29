#!/bin/bash
# Sirve los videos de Ayuda (media/ayuda) tambien por http en iptv2.
#
# El reproductor de los MAG viejos no abre https (por eso sus canales van por
# http) y el navegador del deco no reproduce video: sin una direccion http los
# videos de las guias no se ven en el deco. Solo esa carpeta va por http; todo
# lo demas sigue redirigiendo a https como hasta ahora.
#
# Uso, en iptv2:  sudo bash /var/www/quattretv/deploy/nginx/http_ayuda.sh
# Guarda copia y, si nginx -t falla, la deja como estaba.
set -e
F=/etc/nginx/sites-available/iptv2
cp -a "$F" "$F.antes-http-ayuda-$(date +%Y%m%d-%H%M%S)"
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
viejo = '''server {
    if ($host = iptv2.quattre.com) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    server_name iptv2.quattre.com;
    return 404; # managed by Certbot


}'''
nuevo = '''server {
    listen 80;
    server_name iptv2.quattre.com;

    # Los videos de Ayuda, por http: el reproductor de los MAG viejos no abre https.
    location /media/ayuda/ { alias /var/www/quattretv/media/ayuda/; expires 7d; }

    location / { return 301 https://$host$request_uri; }
}'''
if 'location /media/ayuda/' in s:
    print('ya estaba hecho'); sys.exit(0)
if s.count(viejo) != 1:
    print('el bloque del puerto 80 no es el esperado: no toco nada'); sys.exit(1)
open(p, 'w').write(s.replace(viejo, nuevo))
print('bloque del puerto 80 cambiado')
PY
if nginx -t; then
    systemctl reload nginx
    echo "Hecho. Prueba: curl -sI http://iptv2.quattre.com/media/ayuda/basico.mp4"
else
    cp -a "$(ls -t $F.antes-http-ayuda-* | head -1)" "$F"
    echo "nginx -t ha fallado: restaurado como estaba"; exit 1
fi
