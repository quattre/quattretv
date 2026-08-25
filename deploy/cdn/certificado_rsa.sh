#!/bin/bash
# Añade un certificado RSA al CDN, junto al ECDSA que ya tiene.
#
# Por que: el certificado que emite Let's Encrypt por defecto es ECDSA, y hay
# aparatos antiguos — decos MAG sobre todo — cuyo TLS solo entiende RSA. Con uno
# solo, esos aparatos no se conectan y se quedan en negro.
#
# nginx sabe servir los dos a la vez y elegir segun lo que el cliente diga que
# entiende. Asi que esto no sustituye nada: **añade**. Un navegador moderno o la
# television de LG siguen recibiendo el ECDSA, que es mas ligero, y un deco viejo
# recibe el RSA.
#
# Lo que NO arregla: si el aparato no tiene la raiz de Let's Encrypt (ISRG Root
# X1) en su lista de autoridades de confianza, no hay certificado gratuito que
# valga y habria que comprar uno de una autoridad mas antigua. Esto se sabra al
# probarlo en el deco.
#
# Uso:
#   sudo ./certificado_rsa.sh cdn11.quattre.com
#
# Para deshacerlo: quitar del fichero las dos lineas que acaban en -rsa y
# recargar nginx. El certificado ECDSA no se toca en ningun momento.
#
set -euo pipefail

DOMINIO="${1:-}"
CONF=/etc/nginx/conf.d/hls-ssl.conf
WEBROOT=/var/www/html

if [ -z "$DOMINIO" ]; then
  echo "Falta el dominio. Ej: sudo $0 cdn11.quattre.com" >&2
  exit 1
fi
if [ "$(id -u)" != "0" ]; then
  echo "Esto necesita root: sudo $0 $DOMINIO" >&2
  exit 1
fi
if [ ! -f "$CONF" ]; then
  echo "No existe $CONF. Lanza antes poner_https.sh." >&2
  exit 1
fi

echo "== 1. Como esta ahora =="
canal=$(ls -1 /dev/shm/hls 2>/dev/null | head -1)
antes_1500=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:1500/hls/$canal/index.m3u8" || echo 000)
antes_443=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$DOMINIO/hls/$canal/index.m3u8" || echo 000)
echo "   puerto 1500: $antes_1500   puerto 443: $antes_443"
echo "   certificado actual:"
echo | openssl s_client -connect "$DOMINIO:443" -servername "$DOMINIO" 2>/dev/null \
  | openssl x509 -noout -text 2>/dev/null | grep -E 'Public Key Algorithm' | sed 's/^/     /'

echo "== 2. Certificado RSA =="
if [ -f "/etc/letsencrypt/live/$DOMINIO-rsa/fullchain.pem" ]; then
  echo "   ya existe, no se pide otra vez"
else
  certbot certonly --webroot -w "$WEBROOT" -d "$DOMINIO" \
    --cert-name "$DOMINIO-rsa" --key-type rsa --rsa-key-size 2048 \
    --non-interactive --agree-tos --register-unsafely-without-email \
    --deploy-hook "systemctl reload nginx"
fi
openssl x509 -noout -subject -dates -in "/etc/letsencrypt/live/$DOMINIO-rsa/fullchain.pem" | sed 's/^/   /'

echo "== 3. Añadirlo a nginx, sin quitar el que hay =="
if grep -q -- "-rsa/fullchain.pem" "$CONF"; then
  echo "   ya estaba puesto"
else
  cp "$CONF" "$CONF.bak-$(date +%Y%m%d-%H%M)"
  # nginx admite varios pares certificado/clave y elige segun el cliente.
  python3 - "$CONF" "$DOMINIO" <<'PY'
import sys
conf, dominio = sys.argv[1], sys.argv[2]
s = open(conf).read()
ancla = "    ssl_certificate_key /etc/letsencrypt/live/%s/privkey.pem;\n" % dominio
extra = ancla + (
    "    # Segundo par, en RSA, para los aparatos que no entienden ECDSA.\n"
    "    # nginx elige solo segun lo que el cliente diga que admite.\n"
    "    ssl_certificate     /etc/letsencrypt/live/%s-rsa/fullchain.pem;\n"
    "    ssl_certificate_key /etc/letsencrypt/live/%s-rsa/privkey.pem;\n" % (dominio, dominio)
)
assert s.count(ancla) == 1, 'no encuentro la linea de la clave tal cual esperaba'
open(conf, 'w').write(s.replace(ancla, extra))
print('   añadido')
PY
fi

echo "== 4. Comprobar y recargar =="
if ! nginx -t; then
  echo "   configuracion invalida: se restaura la copia" >&2
  cp "$(ls -t $CONF.bak-* | head -1)" "$CONF"
  nginx -t
  exit 1
fi
systemctl reload nginx
sleep 2

echo "== 5. Que sigue todo en pie =="
d1500=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:1500/hls/$canal/index.m3u8" || echo 000)
d443=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$DOMINIO/hls/$canal/index.m3u8" || echo 000)
echo "   puerto 1500: $antes_1500 -> $d1500"
echo "   puerto 443:  $antes_443 -> $d443"
echo "   ffmpeg en marcha: $(pgrep -fc 'ffmpeg -loglevel' || echo 0)"

echo "== 6. Que certificado recibe cada cliente =="
echo -n "   un cliente moderno (admite ECDSA): "
echo | openssl s_client -connect "$DOMINIO:443" -servername "$DOMINIO" 2>/dev/null \
  | openssl x509 -noout -text 2>/dev/null | grep -oE 'id-ecPublicKey|rsaEncryption' | head -1
echo -n "   un cliente antiguo (solo RSA):      "
echo | openssl s_client -connect "$DOMINIO:443" -servername "$DOMINIO" \
  -cipher 'aRSA' -sigalgs 'RSA+SHA256' 2>/dev/null \
  | openssl x509 -noout -text 2>/dev/null | grep -oE 'id-ecPublicKey|rsaEncryption' | head -1

if [ "$d1500" != "200" ] || [ "$d443" != "200" ]; then
  echo "   *** algo no responde. Deshaz con:" >&2
  echo "       cp $(ls -t $CONF.bak-* | head -1) $CONF && nginx -t && systemctl reload nginx" >&2
  exit 1
fi
echo
echo "LISTO. Ahora prueba el deco: si sigue sin verse, el problema es su lista de"
echo "autoridades de confianza y ningun certificado gratuito lo va a arreglar."
