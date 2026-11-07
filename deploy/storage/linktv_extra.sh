#!/bin/bash
# Canales nuevos para los grabadores sin tocar la tabla de dumpstream.
#
# dumpstream no graba del multicast: su funcion linktv() traduce cada direccion
# de Ministra (udp://239.20.x.x:5004) a la HLS del CDN, escrita a fuego en el
# codigo. Un canal que no este ahi sale grabado vacio. Esto le pone delante un
# gancho que mira primero canales_extra.txt (direccion puerto enlace, uno por
# linea) en la misma carpeta y, si no esta, sigue con la tabla de siempre: los
# canales que ya graban no cambian.
#
# Uso, como root, con la carpeta del grabador:
#   sudo bash linktv_extra.sh /var/www/stalker_portal/quattretv_storage     (el nuestro de record1)
#   sudo bash linktv_extra.sh /var/www/stalker_portal/storage               (el de Ministra)
#   sudo bash linktv_extra.sh <carpeta> --probar     solo dice lo que haria
#   sudo bash linktv_extra.sh <carpeta> --deshacer   vuelve a dejar el dumpstream de antes
#
# Se puede lanzar las veces que haga falta: el gancho se pone una sola vez y las
# lineas de CANALES se añaden o se actualizan. Las grabaciones en curso siguen:
# un dumpstream que ya corre no relee el fichero.
set -euo pipefail

# direccion puerto enlace del CDN (el mismo :1500 que usa la tabla de Ministra).
# 07/11/2026: los 20 canales de la plataforma nueva sin direccion de Ministra
# (multicast_url del canal -> su HLS en el CDN, sacado de iptv2).
CANALES=(
    "234.5.2.116 20000 http://cdn11.quattre.com:1500/hls/canal33/index.m3u8"   # Canal 33
    "234.5.2.117 20000 http://cdn11.quattre.com:1500/hls/sport3/index.m3u8"   # Esport 3
    "234.5.2.10 20000 http://cdn11.quattre.com:1500/hls/a3series/index.m3u8"   # Atreseries
    "239.20.70.4 5004 http://cdn10.quattre.com:1500/hls/ten/index.m3u8"   # Ten
    "234.5.2.39 20000 http://cdn10.quattre.com:1500/hls/13tv/index.m3u8"   # 13TV
    "239.20.10.2 5004 http://cdn11.quattre.com:1500/hls/paramount/index.m3u8"   # Squirrel dos
    "224.168.11.101 20000 http://cdn10.quattre.com:1500/hls/buenviaje/index.m3u8"   # AMC Western
    "239.110.120.5 6000 http://cdn11.quattre.com:1500/hls/iberalia_caza/index.m3u8"   # Iberalia Caza
    "239.110.120.4 6000 http://cdn11.quattre.com:1500/hls/iberalia_pesca/index.m3u8"   # Iberalia Pesca
    "224.168.11.173 2173 http://cdn11.quattre.com:1500/hls/decasa/index.m3u8"   # AMC Living
    "239.20.70.3 5004 http://cdn10.quattre.com:1500/hls/realmadridtv/index.m3u8"   # Real Madrid TV
    "239.10.100.5 5004 http://cdn10.quattre.com:1500/hls/eurosport1/index.m3u8"   # Eurosport 1
    "234.5.2.44 20000 http://cdn10.quattre.com:1500/hls/24h/index.m3u8"   # 24 Horas
    "234.5.2.137 20000 http://cdn10.quattre.com:1500/hls/intereconomia/index.m3u8"   # Intereconomia
    "234.5.2.118 20000 http://cdn10.quattre.com:1500/hls/extremaduratv/index.m3u8"   # Extremadura TV
    "234.5.2.131 20000 http://cdn11.quattre.com:1500/hls/etb1/index.m3u8"   # ETB 1
    "234.5.2.132 20000 http://cdn10.quattre.com:1500/hls/etb2/index.m3u8"   # ETB 2
    "239.20.60.1 5004 http://cdn10.quattre.com:1500/hls/valenciatv/index.m3u8"   # 7 Valencia TV
    "239.20.100.1 5004 http://cdn10.quattre.com:1500/hls/laochomed/index.m3u8"   # La 8 Mediterraneo
    "239.20.60.2 5004 http://cdn11.quattre.com:1500/hls/levantetv/index.m3u8"   # Levante TV
)

CARPETA="${1:-}"
MODO=instalar
case "${2:-}" in
    --probar) MODO=probar ;;
    --deshacer) MODO=deshacer ;;
    "") ;;
    *) echo "Uso: $0 <carpeta del grabador> [--probar|--deshacer]"; exit 2 ;;
esac
DUMP="$CARPETA/dumpstream"
TABLA="$CARPETA/canales_extra.txt"
COPIA="$DUMP.antes-linktv-extra"

[ -n "$CARPETA" ] && [ -f "$DUMP" ] || { echo "No encuentro $DUMP"; exit 1; }
[ "$(id -u)" = 0 ] || [ "$MODO" = probar ] || { echo "Hay que lanzarlo con sudo"; exit 1; }
PY=$(command -v python2 || command -v python || command -v python3)

if [ "$MODO" = deshacer ]; then
    [ -f "$COPIA" ] || { echo "No hay copia $COPIA: nada que deshacer"; exit 1; }
    cp -a "$COPIA" "$DUMP"
    echo "dumpstream devuelto a como estaba. $TABLA se queda (sin el gancho no se usa)."
    exit 0
fi

GANCHO=$(mktemp)
trap 'rm -f "$GANCHO"' EXIT
cat > "$GANCHO" <<'EOF'
def linktv(ip, port):
    # canales_extra.txt: canales que no estan en la tabla de abajo (linktv_extra.sh)
    tabla = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'canales_extra.txt')
    try:
        for linea in open(tabla):
            partes = linea.split('#')[0].split()
            if len(partes) == 3 and partes[0] == ip.replace('udp://', '') and partes[1] == str(port):
                return partes[2]
    except IOError:
        pass
    return linktv_ministra(ip, port)

def linktv_ministra(ip, port):
EOF

if grep -q '^def linktv_ministra(ip, port):' "$DUMP"; then
    echo "El gancho ya estaba en $DUMP"
elif grep -q '^def linktv(ip, port):' "$DUMP"; then
    echo "+ gancho en $DUMP (copia en $COPIA)"
    if [ "$MODO" != probar ]; then
        cp -a "$DUMP" "$COPIA"
        sed -i "/^def linktv(ip, port):/{
r $GANCHO
d
}" "$DUMP"
        if ! "$PY" -c "import sys; compile(open(sys.argv[1]).read(), sys.argv[1], 'exec')" "$DUMP"; then
            cp -a "$COPIA" "$DUMP"
            echo "ERROR: el dumpstream parcheado no compila; devuelto a como estaba"
            exit 1
        fi
    fi
else
    echo "ERROR: no encuentro 'def linktv(ip, port):' en $DUMP"; exit 1
fi

for canal in "${CANALES[@]}"; do
    read -r ip puerto enlace <<<"$canal"
    if [ -f "$TABLA" ] && grep -q "^$ip $puerto " "$TABLA"; then
        echo "+ actualizo $ip:$puerto -> $enlace"
        [ "$MODO" = probar ] || sed -i "s#^$ip $puerto .*#$ip $puerto $enlace#" "$TABLA"
    else
        echo "+ añado $ip:$puerto -> $enlace"
        [ "$MODO" = probar ] || echo "$ip $puerto $enlace" >> "$TABLA"
    fi
done
[ "$MODO" = probar ] && { echo "(simulacro: no se ha cambiado nada)"; exit 0; }
chown --reference="$DUMP" "$TABLA"
chmod 644 "$TABLA"

echo
echo "Tabla $TABLA:"
cat "$TABLA"
for canal in "${CANALES[@]}"; do
    read -r ip puerto enlace <<<"$canal"
    codigo=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$enlace" || true)
    echo "$enlace -> $codigo"
done
