#!/bin/bash
# La puerta "iptv1" en la plataforma nueva, para poder apagar Ministra.
#
# Todos los decos llevan grabado http://iptv1.quattre.com/quattretv/c/ (portal)
# y http://iptv1.quattre.com/firmware/<modelo>/imageupdate (actualizacion). Hoy
# ese nombre llega al nginx de la maquina de Ministra, que pasa los decos a
# iptv2. Esto pone en el nginx de iptv2 un servidor que contesta a ese nombre
# por el puerto 80 igual que hoy: el portal y su API van a la aplicacion, y el
# firmware y la guia salen de disco. No cambia nada para nadie hasta que el
# nombre iptv1 (DNS o NAT del 185.25.27.50:80) se apunte aqui.
#
# Uso, en iptv2 y con sudo:
#   sudo bash puerta_iptv1.sh --probar     dice lo que haria
#   sudo bash puerta_iptv1.sh              instala y recarga nginx
#   sudo bash puerta_iptv1.sh --deshacer   lo quita
# Antes: copiar /var/www/firmware de la maquina de Ministra a /var/www/firmware.
# Prueba sin tocar el DNS: un deco con el portal http://185.25.27.51/quattretv/c/
set -euo pipefail

SITIO=/etc/nginx/sites-available/iptv1
ENLACE=/etc/nginx/sites-enabled/iptv1
FIRMWARE=/var/www/firmware
GUIA=/var/www/epg

MODO=instalar
case "${1:-}" in
    --probar) MODO=probar ;;
    --deshacer) MODO=deshacer ;;
    "") ;;
    *) echo "Uso: $0 [--probar|--deshacer]"; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || [ "$MODO" = probar ] || { echo "Hay que lanzarlo con sudo"; exit 1; }

if [ "$MODO" = deshacer ]; then
    rm -f "$ENLACE" "$SITIO"
    nginx -t && systemctl reload nginx
    echo "Quitado."
    exit 0
fi

grep -q 'upstream quattretv' /etc/nginx/sites-enabled/iptv2 || { echo "ERROR: no encuentro el upstream quattretv"; exit 1; }
for m in 256 322 520 524 540; do
    [ -s "$FIRMWARE/$m/imageupdate" ] || echo "AVISO: falta $FIRMWARE/$m/imageupdate (los decos $m no podrian actualizarse)"
done

CONF=$(cat <<'EOF'
# Puerta iptv1 (deploy/iptv2/puerta_iptv1.sh). Los decos solo hablan http.
server {
    listen 80;
    server_name iptv1.quattre.com iptv1.quattre 185.25.27.51;

    access_log /var/log/nginx/iptv1.access.log;
    error_log  /var/log/nginx/iptv1.error.log;

    location /firmware/ { alias /var/www/firmware/; }
    location /epg/      { alias /var/www/epg/; }
    location /static/   { alias /var/www/quattretv/staticfiles/; expires 7d; }
    location /media/    { alias /var/www/quattretv/media/;       expires 7d; }

    # Como el Apache de Ministra: /quattretv es /stalker_portal.
    location ~ ^/quattretv(/.*)?$ { return 301 /stalker_portal$1; }

    location / {
        proxy_pass http://quattretv;
        proxy_set_header Host iptv2.quattre.com;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
        proxy_read_timeout 120s;
    }
}
EOF
)
echo "+ $SITIO"; echo "$CONF"
[ "$MODO" = probar ] && { echo "(simulacro: no se ha cambiado nada)"; exit 0; }
mkdir -p "$FIRMWARE" "$GUIA"
echo "$CONF" > "$SITIO"
ln -sf "$SITIO" "$ENLACE"
if nginx -t; then systemctl reload nginx; echo "nginx recargado."; else rm -f "$ENLACE"; echo "ERROR: nginx no lo acepta; quitado."; exit 1; fi
curl -s -o /dev/null -w "portal por la puerta: %{http_code}\n" -H 'Host: iptv1.quattre.com' http://127.0.0.1/stalker_portal/c/index.html
