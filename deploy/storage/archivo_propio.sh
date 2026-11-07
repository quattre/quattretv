#!/bin/bash
# Archivo (catchup) de los canales que Ministra no archiva, en record1.
#
# storage1 no tiene sitio para ellos (una semana de 18 canales son ~5,5 TB con
# 7 libres); record1 tiene 27 TB y esta ocioso. Nuestra copia del grabador
# (quattretv_storage, la que obedece a iptv2) ya sabe archivar: le falta el
# bucle que pide las tareas, que en Ministra es tvarchivetasks.service. Esto
# pone uno igual para la copia. iptv2 solo le manda los canales que tienen
# "archivo en" este grabador (Channel.archivo_en), asi que no duplica nada del
# archivo de Ministra.
#
# Uso, en record1 y como root:
#   sudo bash archivo_propio.sh --probar     solo comprueba y dice lo que haria
#   sudo bash archivo_propio.sh              instala y arranca
#   sudo bash archivo_propio.sh --deshacer   para y quita el servicio; lo grabado
#                                            se queda en disco
# Ministra no se toca: ni su carpeta, ni su servicio, ni su disco de grabaciones.
set -euo pipefail

COPIA=/var/www/stalker_portal/quattretv_storage
SERVICIO=quattretv-archivo.service
UNIDAD=/etc/systemd/system/$SERVICIO
CADA=300                                             # segundos entre peticiones

MODO=instalar
case "${1:-}" in
    --probar) MODO=probar ;;
    --deshacer) MODO=deshacer ;;
    "") ;;
    *) echo "Uso: $0 [--probar|--deshacer]"; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || [ "$MODO" = probar ] || { echo "Hay que lanzarlo con sudo"; exit 1; }

if [ "$MODO" = deshacer ]; then
    systemctl disable --now "$SERVICIO" 2>/dev/null || true
    rm -f "$UNIDAD"
    systemctl daemon-reload
    echo "Servicio quitado (al pararlo se paran sus dumpstream). Lo grabado sigue en disco."
    exit 0
fi

# 1. Comprobaciones: que sea nuestra copia, que grabe en el disco grande y que
#    no lleve rutas del grabador de Ministra escritas a fuego.
CFG="$COPIA/config.php"
[ -f "$CFG" ] || { echo "No encuentro $CFG"; exit 1; }
leer() { sed -nE "s/.*define\('$1', *'([^']*)'.*/\1/p" "$CFG"; }
NOMBRE=$(leer STORAGE_NAME); DIR=$(leer RECORDS_DIR); API=$(leer API_URL)
echo "Copia: $COPIA   STORAGE_NAME=$NOMBRE   RECORDS_DIR=$DIR"
echo "Obedece a: $API"
case "$API" in *iptv2*) ;; *) echo "ERROR: la copia no obedece a iptv2"; exit 1 ;; esac
case "$DIR" in /var/www/*|"") echo "ERROR: RECORDS_DIR raro: $DIR"; exit 1 ;; esac
MONTAJE=$(findmnt -n -o TARGET -T "$DIR")
[ "$MONTAJE" != / ] || { echo "ERROR: $DIR esta en el disco del sistema"; exit 1; }
echo "Disco de $DIR: $MONTAJE"; df -h "$MONTAJE" | tail -1
[ -f "$COPIA/tvarchivesync.php" ] || { echo "ERROR: no hay $COPIA/tvarchivesync.php"; exit 1; }
FIJAS=$(grep -rlF "/var/www/stalker_portal/storage/" "$COPIA" --include='*.php' --include='*.sh' --include=dumpstream || true)
if [ -n "$FIJAS" ]; then
    echo "ERROR: la copia lleva rutas del grabador de Ministra en:"; echo "$FIJAS"; exit 1
fi
grep -q '^def linktv_ministra(ip, port):' "$COPIA/dumpstream" || { echo "ERROR: falta el gancho de linktv_extra.sh"; exit 1; }
echo "Canales en canales_extra.txt: $(grep -c . "$COPIA/canales_extra.txt" 2>/dev/null || echo 0)"

echo "Lo que le mandaria iptv2 ahora:"
curl -s -m 10 "${API%/}/tv_archive/$NOMBRE" | head -c 600; echo

# 2. Solo video y audio tambien en el archivo: con -map 0 algunos canales
#    llevan pistas de datos con marcas de tiempo rotas y ffmpeg se para (ver
#    copia_grabador.sh, que lo hace en las grabaciones).
if grep -q -- '-sn -map 0 -c copy -f segment' "$COPIA/dumpstream"; then
    echo "+ dumpstream: solo video y audio en el archivo"
    [ "$MODO" = probar ] || sed -i 's/-sn -map 0 -c copy -f segment/-sn -map 0:v? -map 0:a? -c copy -f segment/g' "$COPIA/dumpstream"
fi

# 3. El bucle, como el tvarchivetasks de Ministra pero de la copia.
echo "+ $UNIDAD (cada $CADA s: php tvarchivesync.php en $COPIA)"
[ "$MODO" = probar ] && { echo "(simulacro: no se ha cambiado nada)"; exit 0; }
cat > "$UNIDAD" <<EOF
[Unit]
Description=Archivo de la plataforma nueva (copia del grabador $NOMBRE)
After=network-online.target
Wants=network-online.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$COPIA
ExecStart=/bin/bash -c 'while true; do php $COPIA/tvarchivesync.php; sleep $CADA; done'
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now "$SERVICIO"
sleep 20
systemctl --no-pager --lines=5 status "$SERVICIO" || true
echo "dumpstream de la copia en marcha: $(pgrep -fc "$DIR" || true)"
