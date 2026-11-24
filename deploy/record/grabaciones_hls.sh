#!/bin/bash
# Grabaciones de los clientes en HLS, en record1, sin convertir ni copiar.
#
# Igual que el archivo de storage1 (deploy/storage/archivo_rangos.sh):
# indexar_grabaciones.py apunta donde empieza cada rato de ~10 s de cada
# grabacion, grabacion.php da la lista .m3u8 y trozo.php entrega cada rato tal
# cual, con una firma del middleware. Las grabaciones no se tocan: solo se leen.
# Asi las ven los aparatos que solo saben HLS (la app de Android sin
# actualizar, y LG y Samsung el dia que se quiera).
#
# Uso, en record1:
#   sudo bash grabaciones_hls.sh             instala o actualiza
#   sudo bash grabaciones_hls.sh --deshacer  quita el enlace de Apache y el cron
#                                            (las grabaciones no se tocan nunca)
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
USUARIO=quattre
BASE=/mnt/record1/quattretv/grab_hls                    # en el disco grande
WEB=/var/www/stalker_portal/quattretv_grab/hls          # por donde lo sirve Apache
PROGRAMA=/home/$USUARIO/archivo
LINEA="* * * * * flock -n $PROGRAMA/grabaciones.lock nice -n 10 ionice -c2 -n7 python3 $PROGRAMA/indexar_grabaciones.py --pasada 290 >> $PROGRAMA/grabaciones.log 2>&1"

[ "$(id -u)" = 0 ] || { echo "Hay que lanzarlo con sudo"; exit 1; }

if [ "${1:-}" = --deshacer ]; then
    rm -f "$WEB"
    { sudo -u "$USUARIO" crontab -l 2>/dev/null | grep -v indexar_grabaciones.py || true; } | sudo -u "$USUARIO" crontab -
    echo "Quitado. El indice sigue en $BASE (se borra a mano si no se quiere)."
    exit 0
fi

mountpoint -q /mnt/record1 || { echo "ERROR: /mnt/record1 no esta montado"; exit 1; }
[ -d "$(dirname "$WEB")" ] || { echo "ERROR: no existe $(dirname "$WEB")"; exit 1; }
for f in indexar_archivo.py indexar_grabaciones.py comun.php grabacion.php trozo.php; do
    [ -f "$AQUI/$f" ] || { echo "ERROR: falta $AQUI/$f"; exit 1; }
done
python3 -m py_compile "$AQUI/indexar_archivo.py" "$AQUI/indexar_grabaciones.py"
for f in comun.php grabacion.php trozo.php; do php -l "$AQUI/$f" >/dev/null; done

# 1. Carpetas. El indice lo escribe el cron (quattre) y, si una grabacion aun
#    no lo tiene al pedirla, grabacion.php (Apache): los dos tienen que poder.
install -d -o "$USUARIO" -g "$USUARIO" -m 755 "$BASE" "$PROGRAMA"
install -d -o "$USUARIO" -g "$USUARIO" -m 777 "$BASE/indice"
ln -sfn "$BASE" "$WEB"

# 2. Programas y paginas.
install -o "$USUARIO" -g "$USUARIO" -m 755 "$AQUI/indexar_archivo.py" "$AQUI/indexar_grabaciones.py" "$PROGRAMA/"
install -o "$USUARIO" -g "$USUARIO" -m 644 "$AQUI/comun.php" "$AQUI/grabacion.php" "$AQUI/trozo.php" "$BASE/"
# El secreto de las firmas: se crea una vez y no sale de aqui ni del .env de
# iptv2 (GRABACIONES_HLS_SECRETO). Pedido directamente no enseña nada.
if [ ! -s "$BASE/secreto.php" ]; then
    printf "<?php return '%s';\n" "$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')" > "$BASE/secreto.php"
    chown "$USUARIO:$USUARIO" "$BASE/secreto.php"
    chmod 644 "$BASE/secreto.php"
fi

# 3. El cron del usuario, cada minuto (lo nuevo primero).
{ sudo -u "$USUARIO" crontab -l 2>/dev/null | grep -v indexar_grabaciones.py || true; echo "$LINEA"; } | sudo -u "$USUARIO" crontab -

echo "Instalado. Comprobacion por Apache (tiene que dar 403, sin firma):"
curl -s -o /dev/null -w '  %{http_code}\n' "http://127.0.0.1:88/stalker_portal/quattretv_grab/hls/grabacion.php?d=nuevas&f=1_20260101000000.mpg&e=1&s=x" || true
sudo -u "$USUARIO" crontab -l | grep indexar_grabaciones.py
