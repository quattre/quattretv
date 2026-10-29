#!/bin/bash
# Añade a iptv2 un certificado RSA junto al ECDSA que ya tiene (como
# deploy/cdn/certificado_rsa.sh hace en los CDN).
#
# Dentro del deco hay dos programas: el navegador, que abre el portal y entiende
# ECDSA, y el reproductor, que pone canales y videos y solo entiende RSA. Con un
# solo certificado ECDSA el reproductor no conecta por https (por eso los decos
# viejos ven los canales por http) y no puede abrir los videos de Ayuda.
# nginx sirve los dos y elige segun el cliente: nadie pierde nada.
#
# Uso, en iptv2:  sudo bash /var/www/quattretv/deploy/nginx/certificado_rsa_iptv2.sh
# Para deshacerlo: quitar las dos lineas que acaban en -rsa y recargar nginx.
set -euo pipefail
D=iptv2.quattre.com
CONF=/etc/nginx/sites-available/iptv2
[ "$(id -u)" = "0" ] || { echo "Esto necesita root: sudo $0"; exit 1; }

echo "== 1. Certificado RSA =="
if [ -f "/etc/letsencrypt/live/$D-rsa/fullchain.pem" ]; then
  echo "   ya existe"
else
  certbot certonly --nginx -d "$D" --cert-name "$D-rsa" --key-type rsa --rsa-key-size 2048 \
    --non-interactive --agree-tos --register-unsafely-without-email \
    --deploy-hook "systemctl reload nginx"
fi

echo "== 2. Añadirlo a nginx, sin quitar el que hay =="
if grep -q -- "$D-rsa/fullchain.pem" "$CONF"; then
  echo "   ya estaba puesto"
else
  cp -a "$CONF" "$CONF.antes-rsa-$(date +%Y%m%d-%H%M%S)"
  python3 - "$CONF" "$D" <<'PY'
import sys
conf, d = sys.argv[1], sys.argv[2]
s = open(conf).read()
ancla = "    ssl_certificate_key /etc/letsencrypt/live/%s/privkey.pem; # managed by Certbot\n" % d
extra = ancla + (
    "    # Segundo par, en RSA, para el reproductor de los decos (no entiende ECDSA).\n"
    "    ssl_certificate     /etc/letsencrypt/live/%s-rsa/fullchain.pem;\n"
    "    ssl_certificate_key /etc/letsencrypt/live/%s-rsa/privkey.pem;\n" % (d, d))
assert s.count(ancla) == 1, 'no encuentro la linea de la clave tal cual esperaba'
open(conf, 'w').write(s.replace(ancla, extra))
print('   añadido')
PY
fi

echo "== 3. Comprobar y recargar =="
if nginx -t; then
  systemctl reload nginx
else
  cp -a "$(ls -t $CONF.antes-rsa-* | head -1)" "$CONF"
  echo "   nginx -t ha fallado: restaurado como estaba"; exit 1
fi
sleep 1
echo -n "   un cliente que solo entiende RSA ahora recibe: "
echo | openssl s_client -connect "$D:443" -servername "$D" -tls1_2 -cipher 'ECDHE-RSA-AES128-GCM-SHA256:AES128-SHA' 2>/dev/null \
  | openssl x509 -noout -text 2>/dev/null | grep -m1 'Public Key Algorithm' || echo "nada (algo no ha ido bien)"
