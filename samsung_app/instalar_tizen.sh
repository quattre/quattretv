#!/bin/bash
# Instala Tizen Studio (solo linea de comandos) y el perfil de televisor.
#
# Se usa la version de consola y no la grafica a proposito: para empaquetar,
# firmar e instalar en un televisor no hace falta ninguna ventana, y la completa
# ocupa mucho mas sin aportar nada aqui.
#
# El instalador se baja de download.tizen.org, que es publico y no pide cuenta.
# Lo que SI pide cuenta de Samsung es el certificado de distribucion, y eso se
# hace despues y una sola vez.
#
#   samsung_app/instalar_tizen.sh [carpeta]
set -euo pipefail
VERSION="6.1"
DESTINO="${1:-$HOME/tizen-studio}"
INSTALADOR="/tmp/web-cli_Tizen_Studio_${VERSION}_ubuntu-64.bin"
URL="http://download.tizen.org/sdk/Installer/tizen-studio_${VERSION}/$(basename "$INSTALADOR")"

command -v java >/dev/null || { echo "Falta Java: sudo apt install openjdk-17-jre" >&2; exit 1; }

if [ ! -s "$INSTALADOR" ]; then
    echo "== Bajando el instalador (unos 280 MB) =="
    curl -sSL -o "$INSTALADOR" "$URL"
fi
chmod +x "$INSTALADOR"

echo "== Instalando en $DESTINO =="
"$INSTALADOR" --accept-license "$DESTINO"

TIZEN="$DESTINO/tools/ide/bin/tizen"
GESTOR="$DESTINO/package-manager/package-manager-cli.bin"
[ -x "$TIZEN" ] || { echo "No ha quedado el mandato tizen en $TIZEN" >&2; exit 1; }

echo
echo "== Añadiendo el perfil de television =="
# Sin esto se puede empaquetar para movil pero no para television: falta el
# perfil 'tv' que pide el config.xml.
"$GESTOR" install --accept-license TV-Extension || \
  echo "  (si falla, se instala a mano: $GESTOR)"

echo
echo "== Instalado =="
"$TIZEN" version 2>&1 | head -2
echo
echo "Añade esto a tu ~/.bashrc para no escribir la ruta entera cada vez:"
echo "  export PATH=\"\$PATH:$DESTINO/tools/ide/bin:$DESTINO/tools\""
