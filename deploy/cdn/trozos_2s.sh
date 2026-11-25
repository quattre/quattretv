#!/bin/bash
# Trozos HLS de 2 s en todos los canales de un CDN (en vez de 10 s).
#
# Por que: los decos lentos (MAG322, 256, 420) se bajan un trozo entero antes de
# pintar. AMC va a 2 s desde el 05/11 y en el 322 arranca un 10-20 % antes que
# los de 10 s; en los MAG5xx no cambia nada. Su archivo de 7 dias y sus
# grabaciones salen igual que con 10 s (comprobado el 25/11/2026).
#
# Que hace, canal a canal y de uno en uno:
#   - si la plantilla ffmpeg-hls@.service no admite HLS_TIME (cdn10), la cambia
#     para que lo admita, con copia; sin las variables queda igual que antes;
#   - añade HLS_TIME=2, HLS_LIST=15 y HLS_FLAGS al fichero del canal (copia
#     <canal>.antes-trozos), lo reinicia y espera a ver trozos de 2 s; si no
#     salen en 40 s, deja el canal como estaba;
#   - espera PAUSA segundos antes del siguiente.
# Cada reinicio corta ese canal unos segundos. Los grabadores leen este HLS:
# conviene lanzarlo de madrugada (--a-las 03:00).
#
#   sudo bash trozos_2s.sh --probar              dice lo que haria
#   sudo bash trozos_2s.sh                       todos los canales en marcha, ya
#   sudo bash trozos_2s.sh --a-las 03:00         espera a esa hora y empieza
#   sudo bash trozos_2s.sh amc boing             solo esos
#   sudo bash trozos_2s.sh --deshacer [canales]  vuelve a 10 s con las copias
#
# Para dejarlo corriendo y cerrar la sesion:
#   sudo nohup bash trozos_2s.sh --a-las 03:00 > /home/quattre/trozos_2s.log 2>&1 &
set -u

CANALES_DIR=/home/quattre/canales
PLANTILLA=/etc/systemd/system/ffmpeg-hls@.service
HLS=/dev/shm/hls
PAUSA=20
LINEAS='HLS_TIME=2
HLS_LIST=15
HLS_FLAGS=delete_segments+temp_file+independent_segments'

PROBAR=0; DESHACER=0; HORA=''; ELEGIDOS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --probar) PROBAR=1 ;;
        --deshacer) DESHACER=1 ;;
        --a-las) HORA="$2"; shift ;;
        *) ELEGIDOS+=("$1") ;;
    esac
    shift
done

[ "$(id -u)" = 0 ] || { echo "Hay que lanzarlo con sudo"; exit 1; }
log() { echo "$(date '+%d/%m %H:%M:%S') $*"; }

if [ ${#ELEGIDOS[@]} -eq 0 ]; then
    mapfile -t ELEGIDOS < <(systemctl list-units 'ffmpeg-hls@*' --state=running --no-legend --plain \
        | awk '{print $1}' | sed 's/^ffmpeg-hls@//; s/\.service$//')
fi
log "${#ELEGIDOS[@]} canales: ${ELEGIDOS[*]}"

if [ -n "$HORA" ] && [ $PROBAR = 0 ]; then
    objetivo=$(date -d "$HORA" +%s); ahora=$(date +%s)
    [ "$objetivo" -le "$ahora" ] && objetivo=$(date -d "tomorrow $HORA" +%s)
    log "Esperando hasta $(date -d @"$objetivo" '+%d/%m %H:%M')"
    sleep $((objetivo - ahora))
fi

# La plantilla: que lea las variables (en cdn11 ya lo hace desde el 05/11).
if ! grep -q 'HLS_TIME' "$PLANTILLA"; then
    log "La plantilla no admite HLS_TIME: se cambia (sin variables, igual que antes)"
    if [ $PROBAR = 0 ]; then
        cp -a "$PLANTILLA" "$PLANTILLA.antes-trozos-$(date +%Y%m%d)"
        sed -i 's/-hls_time 10 -hls_list_size 10/-hls_time ${HLS_TIME:-10} -hls_list_size ${HLS_LIST:-10}/; s/-hls_flags delete_segments \\/-hls_flags ${HLS_FLAGS:-delete_segments} \\/' "$PLANTILLA"
        grep -q 'HLS_TIME' "$PLANTILLA" || { log "ERROR: no se pudo cambiar la plantilla; no se toca nada"; cp -a "$PLANTILLA.antes-trozos-$(date +%Y%m%d)" "$PLANTILLA"; exit 1; }
        systemctl daemon-reload
    fi
fi

# Lo que dice la lista del canal: la duracion del ultimo trozo.
ultimo_trozo() { grep -oE 'EXTINF:[0-9.]+' "$HLS/$1/index.m3u8" 2>/dev/null | tail -1 | cut -d: -f2; }

bien=0; mal=0; saltados=0
for c in "${ELEGIDOS[@]}"; do
    f="$CANALES_DIR/$c"
    [ -f "$f" ] || { log "$c: no hay $f, se salta"; saltados=$((saltados+1)); continue; }
    if [ $DESHACER = 1 ]; then
        [ -f "$f.antes-trozos" ] || { log "$c: sin copia .antes-trozos, se deja"; continue; }
        log "$c: vuelve a como estaba"
        [ $PROBAR = 1 ] && continue
        cp -a "$f.antes-trozos" "$f"; systemctl restart "ffmpeg-hls@$c"; sleep "$PAUSA"; continue
    fi
    if grep -q '^HLS_TIME=' "$f"; then
        d=$(ultimo_trozo "$c")
        if [ -n "$d" ] && awk -v d="$d" 'BEGIN{exit !(d < 3.5)}'; then
            log "$c: ya va a 2 s, se deja"; saltados=$((saltados+1)); continue
        fi
        # Como hollywood el 05/11: tiene las variables pero no se reinicio.
        log "$c: tiene HLS_TIME pero sigue con trozos de ${d:-?} s: solo se reinicia"
        [ $PROBAR = 1 ] && continue
        [ -f "$f.antes-trozos" ] || cp -a "$f" "$f.antes-trozos"
    else
        log "$c: a 2 s"
        [ $PROBAR = 1 ] && continue
        cp -a "$f" "$f.antes-trozos"
        printf '%s\n' "$LINEAS" >> "$f"
    fi
    systemctl restart "ffmpeg-hls@$c"
    ok=0
    for i in $(seq 1 20); do
        sleep 2
        d=$(ultimo_trozo "$c")
        if [ -n "$d" ] && awk -v d="$d" 'BEGIN{exit !(d < 3.5)}'; then ok=1; break; fi
    done
    if [ $ok = 1 ]; then
        log "$c: bien (trozo de $d s)"; bien=$((bien+1))
    else
        log "$c: NO salen trozos de 2 s (ultimo: ${d:-ninguno}); se deja como estaba"
        cp -a "$f.antes-trozos" "$f"; systemctl restart "ffmpeg-hls@$c"; mal=$((mal+1))
    fi
    sleep "$PAUSA"
done
log "Hecho: $bien a 2 s, $mal vueltos atras, $saltados sin tocar"
