#!/bin/bash
# Cambia la configuracion de un canal, lo reinicia y comprueba como queda.
#
# Pensado para dos casos concretos, pero vale para cualquier ajuste:
#
#   syfy  -> pasar el audio de MP2 a AAC. Su fichero avisa de que la conversion
#            metia 2,7 s de desfase; puede que fuera un sintoma del bucle de
#            dts_delta_threshold que se arreglo el 19/08/2026. Esto lo mide y lo
#            dice, en vez de dejarlo a la impresion de quien mire la tele.
#   neox  -> quitar una pista de video basura que el origen cuela (declarada
#            como VVC) sin perder las pistas de audio de idioma.
#
# Mide el desfase audio-video ANTES y DESPUES. Si empeora, avisa y deja escrito
# el comando exacto para deshacerlo: la copia del fichero original se guarda.
#
# Uso:
#   sudo ./limpiar_canal.sh <canal> <CLAVE>=<valor>
#
#   sudo ./limpiar_canal.sh syfy TRANSCODE=copy
#   sudo ./limpiar_canal.sh neox 'MAPS=-map 0:v:0 -map 0:a?'
#
set -euo pipefail

CANAL="${1:-}"
CAMBIO="${2:-}"
CONF="/home/quattre/canales/$CANAL"

if [ -z "$CANAL" ] || [ -z "$CAMBIO" ]; then
  echo "Uso: sudo $0 <canal> CLAVE=valor" >&2
  exit 1
fi
[ "$(id -u)" = "0" ] || { echo "Necesita root." >&2; exit 1; }
[ -f "$CONF" ] || { echo "No existe $CONF" >&2; exit 1; }

CLAVE="${CAMBIO%%=*}"
VALOR="${CAMBIO#*=}"

medir() {
  local etiqueta=$1
  local seg
  seg=$(curl -s --max-time 6 "http://localhost:1500/hls/$CANAL/index.m3u8" | grep -m1 '\.ts' || true)
  if [ -z "$seg" ]; then echo "   $etiqueta: el canal no esta emitiendo"; return; fi
  curl -s --max-time 12 -o /dev/shm/_lc.ts "http://localhost:1500/hls/$CANAL/$seg"
  echo "   $etiqueta:"
  ffprobe -hide_banner -v error -show_entries stream=index,codec_type,codec_name \
    -of compact=p=0 /dev/shm/_lc.ts 2>/dev/null | sed 's/^/      /'
  python3 - <<'PY'
import json, subprocess
r = subprocess.run(['ffprobe','-hide_banner','-v','error','-show_entries',
                    'stream=codec_type,start_time','-of','json','/dev/shm/_lc.ts'],
                   capture_output=True, text=True)
try:
    s = json.loads(r.stdout)['streams']
    v = [float(x['start_time']) for x in s if x.get('codec_type')=='video' and x.get('start_time','N/A')!='N/A']
    a = [float(x['start_time']) for x in s if x.get('codec_type')=='audio' and x.get('start_time','N/A')!='N/A']
    if v and a:
        print('      desfase audio-video: %+.3f s' % (a[0]-v[0]))
    else:
        print('      desfase: no se puede medir en este segmento')
except Exception as e:
    print('      desfase: error', str(e)[:40])
PY
  rm -f /dev/shm/_lc.ts
}

echo "== 1. Como esta ahora =="
grep -E "^$CLAVE=" "$CONF" | sed 's/^/   configuracion: /' || echo "   configuracion: (sin $CLAVE)"
medir "salida actual"

COPIA="$CONF.antes-$(date +%Y%m%d-%H%M%S)"
cp "$CONF" "$COPIA"
echo
echo "== 2. Cambiando $CLAVE =="
echo "   copia de seguridad: $COPIA"
if grep -qE "^$CLAVE=" "$CONF"; then
  # Se reescribe la linea entera. Ojo: en estos ficheros los comentarios van en
  # su propia linea a proposito, porque systemd NO los quita si van detras del
  # valor y se los tragaria como parte de la variable.
  python3 - "$CONF" "$CLAVE" "$VALOR" <<'PY'
import sys
conf, clave, valor = sys.argv[1], sys.argv[2], sys.argv[3]
lineas = open(conf).read().split('\n')
for i, l in enumerate(lineas):
    if l.startswith(clave + '='):
        lineas[i] = '%s=%s' % (clave, valor)
open(conf, 'w').write('\n'.join(lineas))
PY
else
  printf '%s=%s\n' "$CLAVE" "$VALOR" >> "$CONF"
fi
grep -E "^$CLAVE=" "$CONF" | sed 's/^/   ahora: /'

echo
echo "== 3. Reiniciando el canal =="
systemctl restart "ffmpeg-hls@$CANAL"
echo -n "   esperando a que vuelva a emitir"
for i in $(seq 1 20); do
  sleep 3; echo -n "."
  curl -s --max-time 4 "http://localhost:1500/hls/$CANAL/index.m3u8" | grep -q '\.ts' && break
done
echo
sleep 12   # que se llenen un par de segmentos antes de medir

echo
echo "== 4. Como ha quedado =="
medir "salida nueva"

echo
echo "== 5. Estado =="
systemctl is-active "ffmpeg-hls@$CANAL" | sed 's/^/   unidad: /'
echo "   canales emitiendo en esta maquina: $(ls -1 /dev/shm/hls | wc -l)"
echo
echo "Si el desfase ha empeorado o algo no cuadra, se deshace con:"
echo "   sudo cp $COPIA $CONF && sudo systemctl restart ffmpeg-hls@$CANAL"
