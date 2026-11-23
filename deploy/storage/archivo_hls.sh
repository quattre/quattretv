#!/bin/bash
# Archivo semanal en HLS en storage1, canal a canal y en paralelo al de siempre.
#
# Guarda en el disco grande los trozos del HLS del directo del CDN, tal cual
# (recoger_hls.py, al lado de este script): sin ffmpeg, sin recodificar, con la
# hora UTC de inicio de cada trozo en el nombre. El middleware monta con ellos
# la lista .m3u8 de cada programa, que abre todo: deco, LG, Samsung, Android y
# navegador. La fuente es la misma que usa hoy dumpstream (su tabla linktv),
# asi que los CDN no notan nada nuevo.
#
# NO cambia lo que ven los clientes: hasta que no se marca el canal en iptv2
# (manage.py migrar_archivo_hls) el archivo se sigue sirviendo del de siempre.
# Ni Ministra, ni dumpstream, ni el archivo actual se tocan.
#
# Uso, en storage1 y como root:
#   sudo bash archivo_hls.sh --probar 349=http://cdn10.quattre.com:1500/hls/la1/index.m3u8
#   sudo bash archivo_hls.sh          349=http://cdn10.quattre.com:1500/hls/la1/index.m3u8
#   sudo bash archivo_hls.sh --parar 349        para ese canal (lo grabado se queda)
#   sudo bash archivo_hls.sh --deshacer         para todos y quita lo instalado
#                                               (lo grabado se queda en disco)
# 349 es el id del canal en iptv2 (La 1). Se pueden poner varios canales.
set -euo pipefail

DISCO=/mnt/storage1
BASE=$DISCO/quattretv/archive_hls                  # en el disco grande, nunca en /
WEB=/var/www/stalker_portal/quattretv_storage/archive_hls   # por donde lo sirve Apache
CANALES=/home/quattre/archivo                       # un fichero por canal: SRC=...
UNIDAD=/etc/systemd/system/quattretv-archive@.service
AQUI="$(cd "$(dirname "$0")" && pwd)"
RECOGER=$CANALES/recoger_hls.py
LIMPIA=/etc/systemd/system/quattretv-archive-cleanup
HORAS=168                                           # una semana, como el de siempre
USUARIO=quattre

MODO=instalar
case "${1:-}" in
    --probar) MODO=probar; shift ;;
    --parar) MODO=parar; shift ;;
    --deshacer) MODO=deshacer; shift ;;
esac
[ "$(id -u)" = 0 ] || [ "$MODO" = probar ] || { echo "Hay que lanzarlo con sudo"; exit 1; }

if [ "$MODO" = parar ]; then
    for c in "$@"; do systemctl disable --now "quattretv-archive@$c" || true; done
    echo "Parado. Lo grabado sigue en $BASE."
    exit 0
fi
if [ "$MODO" = deshacer ]; then
    for u in $(systemctl list-units --all --plain --no-legend 'quattretv-archive@*' | awk '{print $1}'); do
        systemctl disable --now "$u" || true
    done
    systemctl disable --now quattretv-archive-cleanup.timer 2>/dev/null || true
    rm -f "$UNIDAD" "$LIMPIA.service" "$LIMPIA.timer" "$WEB"
    systemctl daemon-reload
    echo "Quitado. Lo grabado sigue en $BASE (se borra a mano si no se quiere)."
    exit 0
fi

# 1. Comprobaciones.
mountpoint -q "$DISCO" || { echo "ERROR: $DISCO no esta montado"; exit 1; }
echo "Disco: $(df -h "$DISCO" | tail -1)"
echo "Sistema: $(df -h / | tail -1)"
PY=$(command -v python3) || { echo "ERROR: no hay python3"; exit 1; }
[ -f "$AQUI/recoger_hls.py" ] || { echo "ERROR: falta $AQUI/recoger_hls.py"; exit 1; }
"$PY" -m py_compile "$AQUI/recoger_hls.py" || { echo "ERROR: recoger_hls.py no compila con $PY"; exit 1; }
echo "python: $PY ($("$PY" --version 2>&1))"
[ -d "$(dirname "$WEB")" ] || { echo "ERROR: no existe $(dirname "$WEB")"; exit 1; }
[ $# -gt 0 ] || echo "(sin canales: solo se instala lo comun)"
for par in "$@"; do
    c=${par%%=*}; src=${par#*=}
    [[ "$c" =~ ^[0-9]+$ ]] && [[ "$src" =~ ^(http|udp):// ]] || { echo "ERROR: '$par' no es id=url"; exit 1; }
    codigo=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$src" || true)
    echo "Canal $c <- $src (contesta $codigo)"
    [ "$codigo" = 200 ] || [[ "$src" == udp://* ]] || { echo "ERROR: la fuente no contesta"; exit 1; }
done
[ "$MODO" = probar ] && { echo "(simulacro: no se ha cambiado nada)"; exit 0; }

# 2. Carpetas y el listado que lee el middleware.
install -d -o "$USUARIO" -g "$USUARIO" -m 755 "$BASE" "$CANALES"
install -o "$USUARIO" -g "$USUARIO" -m 755 "$AQUI/recoger_hls.py" "$RECOGER"
ln -sfn "$BASE" "$WEB"
cat > "$BASE/lista.php" <<'EOF'
<?php
// Trozos del archivo HLS de un canal entre dos instantes, en JSON.
// lista.php?c=349&desde=20261123-160000&hasta=20261123-170000 (UTC, como los nombres)
header('Content-Type: application/json');
header('Cache-Control: no-store');
$c = isset($_GET['c']) ? $_GET['c'] : '';
$desde = isset($_GET['desde']) ? $_GET['desde'] : '00000000-000000';
$hasta = isset($_GET['hasta']) ? $_GET['hasta'] : '99999999-999999';
$hora = '/^\d{8}-\d{6}$/';
if (!preg_match('/^\d{1,6}$/', $c) || !preg_match($hora, $desde) || !preg_match($hora, $hasta)) {
    http_response_code(400);
    echo '[]';
    exit;
}
$dir = __DIR__ . '/' . $c;
$fuera = array();
if (is_dir($dir)) {
    foreach (scandir($dir) as $n) {
        if (substr($n, -3) !== '.ts') continue;
        $t = substr($n, 0, 15);
        if ($t >= $desde && $t <= $hasta) $fuera[] = $n;
    }
}
echo json_encode($fuera);
EOF
chmod 644 "$BASE/lista.php"

# 3. Un recogedor por canal. La hora de los nombres del CDN es la de Madrid:
#    el proceso va con esa zona para pasarla bien a UTC.
cat > "$UNIDAD" <<EOF
[Unit]
Description=Archivo HLS del canal %i
After=network-online.target
Wants=network-online.target
RequiresMountsFor=$DISCO

[Service]
Type=simple
User=$USUARIO
Group=$USUARIO
Environment=TZ=Europe/Madrid
EnvironmentFile=$CANALES/%i
ExecStart=$PY $RECOGER \${SRC} $BASE/%i
Restart=always
RestartSec=5
Nice=5

[Install]
WantedBy=multi-user.target
EOF

# 4. La semana: lo mas viejo se borra cada hora, por fecha del fichero.
cat > "$LIMPIA.service" <<EOF
[Unit]
Description=Limpieza del archivo HLS (mas de $HORAS h)

[Service]
Type=oneshot
User=$USUARIO
ExecStart=/usr/bin/find $BASE -mindepth 2 -type f -name '*.ts' -mmin +$((HORAS*60)) -delete
ExecStart=/usr/bin/find $BASE -mindepth 2 -type f -name '.*.parte' -mmin +60 -delete
EOF
cat > "$LIMPIA.timer" <<EOF
[Unit]
Description=Limpieza periodica del archivo HLS

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now quattretv-archive-cleanup.timer

# 5. Los canales.
for par in "$@"; do
    c=${par%%=*}; src=${par#*=}
    echo "SRC=$src" > "$CANALES/$c"
    chown "$USUARIO:$USUARIO" "$CANALES/$c"
    systemctl enable "quattretv-archive@$c"
    systemctl restart "quattretv-archive@$c"
done

# 6. Comprobacion: trozos nuevos y el listado por Apache.
[ $# -gt 0 ] || exit 0
echo "Esperando 20 s a los primeros trozos..."
sleep 20
for par in "$@"; do
    c=${par%%=*}
    systemctl --no-pager --lines=3 status "quattretv-archive@$c" | head -5 || true
    echo "Trozos de $c: $(ls "$BASE/$c" 2>/dev/null | wc -l)  ultimo: $(ls "$BASE/$c" 2>/dev/null | tail -1)"
    echo "Listado por Apache: $(curl -s -m 5 "http://127.0.0.1:88/stalker_portal/quattretv_storage/archive_hls/lista.php?c=$c" | head -c 120)"
done
