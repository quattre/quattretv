#!/bin/bash
# El archivo de siempre servido en HLS, sin convertir ni copiar nada.
#
# indexar_archivo.py apunta donde empieza cada rato de ~10 s dentro de las
# piezas horarias de dumpstream; rangos.php da ese indice al middleware y
# trozo.php entrega cada rato tal cual. Ni dumpstream ni las piezas se tocan:
# todo lo de aqui solo las lee.
#
# Va con el usuario quattre, sin sudo (cron del usuario y la carpeta
# archive_hls, que ya es suya y ya sirve Apache):
#   bash archivo_rangos.sh            instala o actualiza
#   bash archivo_rangos.sh --quitar   quita el cron (el indice se queda)
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
WEB=/mnt/storage1/quattretv/archive_hls      # Apache: .../quattretv_storage/archive_hls/
PROGRAMA=/home/quattre/archivo
LINEA="* * * * * flock -n $PROGRAMA/indexar.lock nice -n 10 ionice -c2 -n7 python3 $PROGRAMA/indexar_archivo.py --pasada 290 >> $PROGRAMA/indexar.log 2>&1"

if [ "${1:-}" = --quitar ]; then
    { crontab -l 2>/dev/null | grep -v indexar_archivo.py || true; } | crontab -
    echo "Cron quitado. El indice sigue en $WEB/indice."
    exit 0
fi

[ "$(id -un)" = quattre ] || { echo "Con el usuario quattre, sin sudo"; exit 1; }
[ -w "$WEB" ] || { echo "ERROR: no se puede escribir en $WEB"; exit 1; }
python3 -m py_compile "$AQUI/indexar_archivo.py"
php -l "$AQUI/rangos.php" >/dev/null
php -l "$AQUI/trozo.php" >/dev/null

install -d "$PROGRAMA" "$WEB/indice"
install -m 755 "$AQUI/indexar_archivo.py" "$PROGRAMA/indexar_archivo.py"
install -m 644 "$AQUI/rangos.php" "$WEB/rangos.php"
install -m 644 "$AQUI/trozo.php" "$WEB/trozo.php"
{ crontab -l 2>/dev/null | grep -v indexar_archivo.py || true; echo "$LINEA"; } | crontab -
# El log, que no crezca sin fin (el disco del sistema va justo).
if [ -f "$PROGRAMA/indexar.log" ] && [ "$(stat -c %s "$PROGRAMA/indexar.log")" -gt 5000000 ]; then
    tail -n 2000 "$PROGRAMA/indexar.log" > "$PROGRAMA/indexar.log.tmp" && mv "$PROGRAMA/indexar.log.tmp" "$PROGRAMA/indexar.log"
fi
echo "Instalado. El indice se va llenando (lo nuevo primero): $WEB/indice"
crontab -l | grep indexar_archivo.py
