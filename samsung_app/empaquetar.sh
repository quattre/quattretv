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


# Se firma y se empaqueta aqui mismo si Tizen Studio esta instalado.
#
# NO se pasa por 'tizen build-web': en una app web no hay nada que construir, y
# ademas revienta al 80% en la version de consola -- le falta una libreria de
# Eclipse que solo trae la version grafica. El paquete sale identico, byte a
# byte, empaquetando directamente desde la carpeta fuente.
TIZEN="$(command -v tizen || echo "$HOME/tizen-studio/tools/ide/bin/tizen")"
PERFIL="${PERFIL_FIRMA:-quattre}"

if [ ! -x "$TIZEN" ]; then
    echo
    echo "Tizen Studio no esta instalado. Para instalarlo:"
    echo "  samsung_app/instalar_tizen.sh"
    exit 0
fi

echo
echo "== firmando con el perfil '$PERFIL' =="
"$TIZEN" package -t wgt -s "$PERFIL" -- "$SALIDA" 2>&1 | grep -iE "package file|error|fail" || true

WGT="$SALIDA/QuattreTV.wgt"
if [ -f "$WGT" ]; then
    echo
    echo "Listo: $WGT ($(du -h "$WGT" | cut -f1))"
    echo
    echo "Para instalarlo en un televisor con modo desarrollador:"
    echo "  sdb connect <ip-del-televisor>"
    echo "  tizen install -n QuattreTV.wgt -- \"$SALIDA\""
    echo
    echo "OJO: este paquete va firmado con el certificado de pruebas que trae"
    echo "Tizen Studio. Sirve para el Remote Test Lab y para un televisor en modo"
    echo "desarrollador, NO para publicar. Para la tienda hace falta el"
    echo "certificado de distribucion de Samsung, y poner en config.xml el"
    echo "identificador de paquete que ellos asignen -- ahora lleva 'QuattreTV0',"
    echo "que es de mentira."
fi
