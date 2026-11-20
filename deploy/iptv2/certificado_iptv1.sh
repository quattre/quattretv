#!/bin/bash
# https://iptv1.quattre.com en un navegador -> el panel nuevo (iptv2).
#
# Hace dos cosas, y se puede lanzar las veces que haga falta:
#   1. Vuelve a escribir la puerta de los decos (puerta_iptv1.sh), que lleva
#      el nombre a secas por http al panel nuevo.
#   2. Pide a Let's Encrypt un certificado para iptv1.quattre.com y pone un
#      sitio https que solo redirige a https://iptv2.quattre.com. Los
#      certificados de iptv2 no se tocan. Se renueva solo con el certbot que
#      ya hay (certbot.timer).
#
#   sudo bash deploy/iptv2/certificado_iptv1.sh             instala
#   sudo bash deploy/iptv2/certificado_iptv1.sh --deshacer  quita el sitio https
#                                                           (el certificado se queda)
set -u
NOMBRE=iptv1.quattre.com
SITIO=/etc/nginx/sites-available/iptv1-https
ENLACE=/etc/nginx/sites-enabled/iptv1-https
VIVO=/etc/letsencrypt/live/$NOMBRE
AQUI=$(cd "$(dirname "$0")" && pwd)

[ "$(id -u)" = 0 ] || { echo "Hay que lanzarlo con sudo"; exit 1; }

if [ "${1:-}" = --deshacer ]; then
    rm -f "$ENLACE" "$SITIO"
    nginx -t && systemctl reload nginx
    echo "Quitado el sitio https de $NOMBRE."
    exit 0
fi

echo "== 1/2 La puerta de los decos =="
bash "$AQUI/puerta_iptv1.sh" || { echo "ERROR: la puerta no se ha podido escribir; no sigo."; exit 1; }

echo "== 2/2 Certificado de $NOMBRE =="
if [ ! -s "$VIVO/fullchain.pem" ]; then
    certbot certonly --nginx -d "$NOMBRE" --cert-name "$NOMBRE" \
        --non-interactive --agree-tos --deploy-hook "systemctl reload nginx" \
        || { echo "ERROR: Let's Encrypt no ha dado el certificado. La puerta http sigue bien."; exit 1; }
else
    echo "Ya hay certificado: $VIVO"
fi

cat > "$SITIO" <<CONF
# https://iptv1.quattre.com (deploy/iptv2/certificado_iptv1.sh): solo redirige
# al panel, que vive en iptv2. Los decos no usan https.
server {
    listen 443 ssl;
    server_name $NOMBRE;
    ssl_certificate     $VIVO/fullchain.pem;
    ssl_certificate_key $VIVO/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    return 302 https://iptv2.quattre.com\$request_uri;
}
CONF
ln -sf "$SITIO" "$ENLACE"
if nginx -t; then
    systemctl reload nginx; echo "nginx recargado."
else
    rm -f "$ENLACE"; nginx -t && systemctl reload nginx
    echo "ERROR: nginx no acepta el sitio https; quitado. La puerta http sigue bien."; exit 1
fi
sleep 1
curl -s -o /dev/null -w "http  $NOMBRE -> %{http_code} %{redirect_url}\n" --resolve $NOMBRE:80:127.0.0.1 http://$NOMBRE/
curl -s -o /dev/null -w "https $NOMBRE -> %{http_code} %{redirect_url}\n" --resolve $NOMBRE:443:127.0.0.1 https://$NOMBRE/
curl -s -o /dev/null -w "https iptv2 (panel) -> %{http_code}\n" --resolve iptv2.quattre.com:443:127.0.0.1 https://iptv2.quattre.com/admin/login/
curl -s -o /dev/null -w "portal de los decos -> %{http_code}\n" -H "Host: $NOMBRE" http://127.0.0.1/stalker_portal/c/index.html
