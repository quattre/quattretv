#!/bin/bash
# Construye el .ipk con SOLO los ficheros de la app.
#
# Antes se hacia `ares-package lg_app`, que mete la carpeta entera: la fuente
# Antonio, los generadores de Python, la documentacion, los ficheros de prueba,
# el __pycache__ y — lo peor — instalar_tv.sh, que lleva dentro la contraseña
# del modo desarrollador de la television de pruebas. Todo eso se estaria
# instalando en el televisor de cada cliente.
set -e
AQUI="$(cd "$(dirname "$0")" && pwd)"
SALIDA="$AQUI/dist"

# Lo unico que forma parte de la app. Lo que no este aqui, no se empaqueta.
FICHEROS=(appinfo.json index.html icon.png largeIcon.png splash.png)

rm -rf "$SALIDA"
mkdir -p "$SALIDA/app"

for f in "${FICHEROS[@]}"; do
    [ -f "$AQUI/$f" ] || { echo "ERROR: falta $f" >&2; exit 1; }
    cp "$AQUI/$f" "$SALIDA/app/"
done

echo "== se empaqueta esto y nada mas =="
ls -la "$SALIDA/app" | tail -n +2 | awk '{printf "  %8s  %s\n", $5, $9}'

rm -f "$AQUI"/*.ipk
ares-package "$SALIDA/app" -o "$AQUI" >/dev/null

IPK="$(ls -t "$AQUI"/*.ipk | head -1)"
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
