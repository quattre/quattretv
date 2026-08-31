#!/bin/bash
# Construye el .ipk con SOLO los ficheros de la app.
#
# Antes se hacia `ares-package lg_app`, que mete la carpeta entera: la fuente
# Antonio, los generadores de Python, la documentacion, los ficheros de prueba,
# el __pycache__ y — lo peor — instalar_tv.sh, que lleva dentro la contraseña
# del modo desarrollador de la television de pruebas. Todo eso se estaria
# instalando en el televisor de cada cliente.
#
# Se construye DOS veces, una por resolucion de graficos:
#
#   1920x1080 -> televisores UHD
#   1280x720  -> televisores FHD
#
# Hacen falta las dos. Al enviar solo la de 1920x1080, LG avisa de que la app
# "will be excluded from being published on FHD models", que son la mayoria de
# los televisores que hay en las casas. El portal ya sabe pintarse a 720p -- lo
# hace todos los dias en los MAG 520, con la consulta de medios de
# max-width:1400px -- asi que lo unico que cambia entre los dos paquetes es lo
# que declara appinfo.json.
#
#   ./empaquetar.sh            -> el de 1920x1080
#   ./empaquetar.sh 1280x720   -> el de 720p, con su splash a medida
set -e
AQUI="$(cd "$(dirname "$0")" && pwd)"
SALIDA="$AQUI/dist"
RESOLUCION="${1:-1920x1080}"

case "$RESOLUCION" in
  1920x1080) SUFIJO="" ;;
  1280x720)  SUFIJO="_720" ;;
  *) echo "Resolucion no contemplada: $RESOLUCION (usa 1920x1080 o 1280x720)" >&2; exit 1 ;;
esac

# Lo unico que forma parte de la app. Lo que no este aqui, no se empaqueta.
FICHEROS=(appinfo.json index.html icon.png largeIcon.png splash.png)

rm -rf "$SALIDA"
mkdir -p "$SALIDA/app"

for f in "${FICHEROS[@]}"; do
    [ -f "$AQUI/$f" ] || { echo "ERROR: falta $f" >&2; exit 1; }
    cp "$AQUI/$f" "$SALIDA/app/"
done

# La resolucion declarada, y el splash al tamaño que le toca: webOS lo escalaria
# igual, pero escalar 1920 a 720 en el televisor se nota en los bordes de la
# letra, y el splash es lo primero que se ve.
python3 - "$SALIDA/app" "$RESOLUCION" <<'PYFIN'
import json, sys
carpeta, resolucion = sys.argv[1], sys.argv[2]
ruta = carpeta + '/appinfo.json'
d = json.load(open(ruta))
d['resolution'] = resolucion
json.dump(d, open(ruta, 'w'), indent=2, ensure_ascii=False)
if resolucion != '1920x1080':
    try:
        from PIL import Image
        an, al = (int(x) for x in resolucion.split('x'))
        im = Image.open(carpeta + '/splash.png').convert('RGB')
        im.resize((an, al), Image.LANCZOS).save(carpeta + '/splash.png')
        print('   splash reescalado a %s' % resolucion)
    except ImportError:
        print('   (sin Pillow: el splash se queda a 1920x1080 y lo escala el televisor)')
PYFIN
echo "== resolucion declarada: $RESOLUCION =="

echo "== se empaqueta esto y nada mas =="
ls -la "$SALIDA/app" | tail -n +2 | awk '{printf "  %8s  %s\n", $5, $9}'

# ares-package nombra por id y version, asi que los dos paquetes saldrian con el
# mismo nombre y el segundo pisaria al primero sin decir nada. Se genera en una
# carpeta aparte y se mueve ya con su sufijo.
ares-package "$SALIDA/app" -o "$SALIDA" >/dev/null
GENERADO="$(ls -t "$SALIDA"/*.ipk | head -1)"
IPK="$AQUI/$(basename "${GENERADO%.ipk}")$SUFIJO.ipk"
rm -f "$IPK"
mv "$GENERADO" "$IPK"
echo
echo "== comprobando que no se ha colado nada =="
TMP="$(mktemp -d)"
( cd "$TMP" && ar x "$IPK" && tar tzf data.tar.gz \
  | grep 'applications/' | grep -v '/$' | sed 's|.*applications/[^/]*/||' | sort > lista.txt )
cat "$TMP/lista.txt" | sed 's|^|  |'
INTRUSOS="$(comm -23 "$TMP/lista.txt" <(printf '%s\n' "${FICHEROS[@]}" | sort))"
rm -rf "$TMP" "$SALIDA"

if [ -n "$INTRUSOS" ]; then
    echo; echo "ERROR: se ha colado en el paquete:" >&2
    echo "$INTRUSOS" | sed 's|^|  |' >&2
    exit 1
fi
echo
echo "Correcto: $(basename "$IPK") - $(du -h "$IPK" | cut -f1)"
