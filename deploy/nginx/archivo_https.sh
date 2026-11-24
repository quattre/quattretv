#!/bin/bash
# El archivo y las grabaciones en HLS, tambien por https a traves de iptv2.
#
# La app de Android TV solo admite https (usesCleartextTraffic=false) y los
# trozos estan en storage1 (:2142) y record1 (:2222), que solo tienen http: el
# videoclub de 7 dias se quedaba en negro. iptv2 esta en la misma red que los
# dos y ya tiene el certificado, asi que se los pide y los entrega por https.
# Solo se usa para lo que no es deco (HLS_POR_IPTV2 en el .env); los decos
# siguen yendo directos por http.
#
#   /archivo_hls/      -> storage1 .../quattretv_storage/archive_hls/ (rangos.php, trozo.php)
#   /grabaciones_hls/  -> record1  .../quattretv_grab/hls/ (grabacion.php, trozo.php)
#
# Uso, en iptv2:  sudo bash /var/www/quattretv/deploy/nginx/archivo_https.sh
# Guarda copia y, si nginx -t falla, la deja como estaba.
set -e
F=/etc/nginx/sites-available/iptv2
cp -a "$F" "$F.antes-archivo-https-$(date +%Y%m%d-%H%M%S)"
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
if 'location /archivo_hls/' in s:
    print('ya estaba hecho'); sys.exit(0)
ancla = '''    location / {
        proxy_pass http://quattretv;'''
if s.count(ancla) != 1:
    print('el bloque https no es el esperado: no toco nada'); sys.exit(1)
nuevo = '''    # Archivo y grabaciones en HLS por https para la app de Android y las
    # teles (deploy/nginx/archivo_https.sh): se piden a storage1 y record1.
    location /archivo_hls/ {
        proxy_pass http://185.25.27.50:2142/stalker_portal/quattretv_storage/archive_hls/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 60s;
    }
    location /grabaciones_hls/ {
        proxy_pass http://185.25.27.50:2222/stalker_portal/quattretv_grab/hls/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 60s;
    }

'''
open(p, 'w').write(s.replace(ancla, nuevo + ancla))
print('bloque https cambiado')
PY
if nginx -t; then
    systemctl reload nginx
    echo "Hecho. Prueba (tiene que dar 400, sin parametros):"
    curl -s -o /dev/null -w '  archivo %{http_code}\n' https://iptv2.quattre.com/archivo_hls/rangos.php
    curl -s -o /dev/null -w '  grabaciones %{http_code}\n' https://iptv2.quattre.com/grabaciones_hls/grabacion.php
else
    cp -a "$(ls -t $F.antes-archivo-https-* | head -1)" "$F"
    echo "nginx -t ha fallado: restaurado como estaba"; exit 1
fi
