#!/bin/bash
# Prepara la carpeta de la app de Samsung y dice como empaquetarla.
#
# El cargador, el icono y el splash NO se duplican aqui: se toman de lg_app,
# porque son exactamente los mismos y dos copias del mismo fichero acaban
# separandose sin que nadie se de cuenta. Lo unico propio de Samsung es el
# config.xml.
#
# El empaquetado en si lo hace la herramienta de Samsung (Tizen Studio), que no
# esta en esta maquina. Esto deja la carpeta lista y escribe el comando.
#
#   samsung_app/empaquetar.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/.." && pwd)"
SALIDA="$AQUI/dist"

rm -rf "$SALIDA"
mkdir -p "$SALIDA"

cp "$AQUI/config.xml"      "$SALIDA/"
cp "$RAIZ/lg_app/index.html"  "$SALIDA/"
cp "$RAIZ/lg_app/icon.png"    "$SALIDA/"
cp "$RAIZ/lg_app/splash.png"  "$SALIDA/"

echo "== la app de Samsung, lista en $SALIDA =="
ls -la "$SALIDA" | tail -n +2 | awk '{printf "  %8s  %s\n", $5, $9}'

echo
echo "Para empaquetarla y firmarla hace falta Tizen Studio:"
echo
echo "  tizen build-web -- \"$SALIDA\""
echo "  tizen package -t wgt -s <perfil-de-firma> -- \"$SALIDA/.buildResult\""
echo
echo "Y para probarla en un televisor con modo desarrollador:"
echo
echo "  tizen install -n QuattreTV.wgt -t <nombre-del-televisor>"
echo
echo "Antes de enviar hay que poner en config.xml el identificador de paquete"
echo "que asigne Samsung -- ahora lleva 'QuattreTV0', que es de mentira."
