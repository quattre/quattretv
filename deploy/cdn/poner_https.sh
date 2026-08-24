#!/bin/bash
# Anade HTTPS al CDN sin tocar nada de lo que ya funciona.
#
# Lo que hace:
#   - saca un certificado de Let's Encrypt por el puerto 80 que ya esta abierto
#   - crea /etc/nginx/conf.d/hls-ssl.conf, un fichero NUEVO
#   - recarga nginx solo si la configuracion pasa la comprobacion
#
# Lo que NO hace:
#   - no toca hls.conf ni el puerto 1500, que es por donde entran los decos
#     que hay en produccion. Siguen exactamente igual.
#   - no toca ningun ffmpeg, ni systemd, ni los canales
#   - no deja que certbot escriba en la configuracion de nginx (por eso
#     'certonly --webroot' y no el plugin de nginx)
#
# Uso:
#   sudo ./poner_https.sh cdn11.quattre.com --probar   <- ensayo, no saca certificado
#   sudo ./poner_https.sh cdn11.quattre.com            <- de verdad
#
# Para deshacerlo:
#   sudo rm /etc/nginx/conf.d/hls-ssl.conf && sudo nginx -t && sudo systemctl reload nginx
#
set -euo pipefail

DOMINIO="${1:-}"
MODO="${2:-}"
CONF=/etc/nginx/conf.d/hls-ssl.conf
WEBROOT=/var/www/html

# Si pones un correo, Let's Encrypt avisa cuando el certificado esta a punto de
# caducar. Sin el, no avisa nadie. Se pasa asi:
#   EMAIL=alguien@quattre.com sudo -E ./poner_https.sh cdn11.quattre.com
EMAIL="${EMAIL:-}"
if [ -n "$EMAIL" ]; then
  REGISTRO=(-m "$EMAIL")
else
  REGISTRO=(--register-unsafely-without-email)
fi

if [ -z "$DOMINIO" ]; then
  echo "Falta el dominio. Ej: sudo $0 cdn11.quattre.com" >&2
  exit 1
fi
if [ "$(id -u)" != "0" ]; then
  echo "Esto necesita root: sudo $0 $DOMINIO ${MODO}" >&2
  exit 1
fi

echo "== 1. Comprobaciones previas =="

# El dominio tiene que apuntar a esta maquina, si no el certificado no se puede
# validar y ademas estariamos configurando el nombre equivocado.
ip_dominio=$(getent hosts "$DOMINIO" | awk '{print $1}' | head -1)
ip_maquina=$(ip -4 route get 8.8.8.8 2>/dev/null | grep -o 'src [0-9.]*' | cut -d' ' -f2)
echo "   $DOMINIO -> ${ip_dominio:-(no resuelve)}   esta maquina -> $ip_maquina"
if [ "$ip_dominio" != "$ip_maquina" ]; then
  echo "   AVISO: no coinciden. Si hay NAT por medio puede ser normal; si no, para." >&2
fi

# El 443 tiene que estar libre: si algo escucha ahi, no seguimos.
if ss -ltn 2>/dev/null | grep -q ':443 '; then
  echo "   El puerto 443 ya esta ocupado. No sigo." >&2
  exit 1
fi
echo "   puerto 443 libre"

# El 1500 tiene que seguir en pie al final. Guardamos como esta ahora.
canales_antes=$(ls -1 /dev/shm/hls 2>/dev/null | wc -l)
codigo_1500=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
  "http://localhost:1500/hls/$(ls -1 /dev/shm/hls 2>/dev/null | head -1)/index.m3u8" || echo 000)
echo "   canales emitiendo: $canales_antes, puerto 1500 responde $codigo_1500"

# El reto de Let's Encrypt se sirve por el 80, que ya tiene un 'location /'
# con try_files, asi que basta con dejar el fichero en el webroot.
if [ ! -d "$WEBROOT" ]; then
  echo "   No existe $WEBROOT, que es por donde se valida. No sigo." >&2
  exit 1
fi
mkdir -p "$WEBROOT/.well-known/acme-challenge"
echo ok > "$WEBROOT/.well-known/acme-challenge/_prueba"
local80=$(curl -s --max-time 5 "http://localhost/.well-known/acme-challenge/_prueba" || true)
rm -f "$WEBROOT/.well-known/acme-challenge/_prueba"
if [ "$local80" != "ok" ]; then
  echo "   El puerto 80 no sirve el reto desde localhost. No sigo." >&2
  exit 1
fi
echo "   el puerto 80 sirve el reto (desde fuera lo dira certbot)"

echo "== 2. certbot =="
if ! command -v certbot >/dev/null; then
  echo "   instalando..."
  apt-get update -qq
  apt-get install -y -qq certbot
else
  echo "   ya estaba instalado: $(certbot --version 2>&1)"
fi

echo "== 3. Certificado =="
if [ "$MODO" = "--probar" ]; then
  echo "   ENSAYO: se valida el camino pero no se emite certificado."
  certbot certonly --webroot -w "$WEBROOT" -d "$DOMINIO" \
    --non-interactive --agree-tos "${REGISTRO[@]}" \
    --dry-run
  echo
  echo "   El ensayo ha pasado: el puerto 80 se alcanza desde internet."
  echo "   Vuelve a lanzarlo sin --probar para hacerlo de verdad."
  exit 0
fi

if [ -f "/etc/letsencrypt/live/$DOMINIO/fullchain.pem" ]; then
  echo "   ya hay certificado para $DOMINIO, no lo pido otra vez"
else
  certbot certonly --webroot -w "$WEBROOT" -d "$DOMINIO" \
    --non-interactive --agree-tos "${REGISTRO[@]}" \
    --deploy-hook "systemctl reload nginx"
fi
openssl x509 -noout -subject -dates -in "/etc/letsencrypt/live/$DOMINIO/fullchain.pem" | sed 's/^/   /'

echo "== 4. Bloque de nginx para el 443 =="
# Fichero nuevo. hls.conf no se toca: el 1500 se queda como esta.
[ -f "$CONF" ] && cp -n "$CONF" "$CONF.bak-$(date +%Y%m%d)" || true
cat > "$CONF" <<CONFEOF
# HLS por HTTPS. Sirve exactamente lo mismo que el puerto 1500 de hls.conf,
# desde el mismo /dev/shm. El 1500 sigue en pie para los decos que ya estan
# en produccion; esto es una puerta mas, no un cambio.
#
# Lo genero deploy/cdn/poner_https.sh. Para quitarlo: borrar este fichero,
# nginx -t y systemctl reload nginx.
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMINIO;

    ssl_certificate     /etc/letsencrypt/live/$DOMINIO/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMINIO/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

    gzip off;
    root /dev/shm;

    location ~* ^/hls/.*\.ts\$ {
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Headers Range;
        add_header Access-Control-Expose-Headers Content-Length,Content-Range;

        types { video/mp2t ts; }
        default_type video/mp2t;

        add_header Cache-Control "public, max-age=60, immutable";
        expires 60s;

        open_file_cache max=20000 inactive=30s;
        sendfile on;
        tcp_nopush on;
        try_files \$uri =404;
    }

    location ~* ^/hls/.*\.m3u8\$ {
        add_header Access-Control-Allow-Origin *;
        try_files \$uri =404;
    }

    location / { return 404; }
}
CONFEOF
echo "   escrito $CONF"

echo "== 5. Comprobar antes de recargar =="
if ! nginx -t; then
  echo "   la configuracion NO es valida: quito el fichero y lo dejo como estaba" >&2
  rm -f "$CONF"
  nginx -t
  exit 1
fi

echo "== 6. Recargar =="
# recargar no corta las conexiones en curso ni toca los ffmpeg
systemctl reload nginx
sleep 2

echo "== 7. Que nada se ha movido =="
canal=$(ls -1 /dev/shm/hls 2>/dev/null | head -1)
canales_despues=$(ls -1 /dev/shm/hls 2>/dev/null | wc -l)
c1500=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:1500/hls/$canal/index.m3u8" || echo 000)
c443=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$DOMINIO/hls/$canal/index.m3u8" || echo 000)
echo "   canales emitiendo: $canales_antes antes -> $canales_despues ahora"
echo "   puerto 1500 (los decos de produccion): $codigo_1500 antes -> $c1500 ahora"
echo "   puerto 443 (nuevo, para la LG):        $c443"
echo "   ffmpeg en marcha: $(pgrep -fc 'ffmpeg -loglevel' || echo 0)"

if [ "$c1500" != "200" ]; then
  echo "   *** EL 1500 HA DEJADO DE RESPONDER: deshaz con"
  echo "       rm $CONF && nginx -t && systemctl reload nginx" >&2
  exit 1
fi
if [ "$c443" != "200" ]; then
  echo "   El 443 no sirve todavia (puede ser el cortafuegos perimetral)." >&2
  echo "   El 1500 sigue bien, asi que produccion no esta afectada." >&2
  exit 1
fi

echo
echo "LISTO. https://$DOMINIO/hls/$canal/index.m3u8 responde, y el 1500 sigue igual."
echo "Renovacion automatica: $(systemctl is-active certbot.timer 2>/dev/null || echo 'revisar certbot.timer')"
