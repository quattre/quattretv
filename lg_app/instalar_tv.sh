#!/bin/bash
# Instala y lanza la app QuattreTV en la LG TV (modo desarrollador).
# Localiza la TV automaticamente por la red (puerto 9922 del modo dev),
# actualiza la config de ares, instala el .ipk y lanza la app.
set -e

DEVICE="lgtv"
APP_ID="com.quattre.tv"
IPK_DIR="$(cd "$(dirname "$0")" && pwd)"
IPK="$(ls -t "$IPK_DIR"/*.ipk 2>/dev/null | head -1)"
SUBNET="192.168.200.0/24"
PASSPHRASE="A68DD3"   # passphrase del modo dev de esta TV (se ve en la app Developer Mode)

if [ -z "$IPK" ]; then
  echo "ERROR: no encuentro ningun .ipk en $IPK_DIR" >&2
  exit 1
fi
echo ">> Paquete: $IPK"

echo ">> Buscando la TV en la red (puerto 9922)..."
TV_IP="$(nmap -p 9922 --open -T4 -n "$SUBNET" 2>/dev/null \
         | grep -B4 '9922/tcp open' | grep 'scan report' \
         | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -1)"

if [ -z "$TV_IP" ]; then
  echo "ERROR: no encuentro ninguna TV con modo desarrollador activo." >&2
  echo >&2
  echo "  La sesion de modo desarrollador de LG caduca a las 50 horas, y al" >&2
  echo "  caducar se lleva la app por delante. Hay que renovarla EN LA TELE," >&2
  echo "  no se puede hacer por red:" >&2
  echo >&2
  echo "    1. Abre la app 'Developer Mode' en la LG" >&2
  echo "    2. Pulsa 'Extend session' (o reactiva 'Dev Mode Status')" >&2
  echo "    3. Vuelve a lanzar este script" >&2
  echo >&2
  echo "  Para dejar de depender de esto hay que publicar la app en la LG" >&2
  echo "  Content Store, que ya es posible: exigia HTTPS y el portal ya lo" >&2
  echo "  tiene en https://iptv2.quattre.com" >&2
  exit 1
fi
echo ">> TV encontrada en: $TV_IP"

echo ">> Configurando dispositivo '$DEVICE'..."
ares-setup-device --modify "$DEVICE" \
  --info "host=$TV_IP" \
  --info "port=9922" \
  --info "username=prisoner" \
  --info "passphrase=$PASSPHRASE" >/dev/null 2>&1 \
  || ares-setup-device --add "$DEVICE" \
       --info "host=$TV_IP" \
       --info "port=9922" \
       --info "username=prisoner" \
       --info "passphrase=$PASSPHRASE" >/dev/null 2>&1

echo ">> Instalando la app..."
ares-install --device "$DEVICE" "$IPK"

echo ">> Lanzando la app..."
ares-launch --device "$DEVICE" "$APP_ID"

echo ">> Hecho. QuattreTV instalada y lanzada en $TV_IP"
