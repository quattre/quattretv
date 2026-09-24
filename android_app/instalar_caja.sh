#!/bin/bash
# Instala y lanza la app en una caja Android TV real (Xiaomi TV Box S, etc.)
# por red, y deja el registro en pantalla.
#
#   ./instalar_caja.sh 192.168.200.xx
#
# En la caja, una sola vez:
#   Ajustes -> Sistema -> Información -> pulsar 7 veces sobre "Compilación"
#   Ajustes -> Sistema -> Opciones para desarrolladores -> "Depuración por USB": SI
#   (la IP sale en Ajustes -> Red e Internet -> la wifi/cable conectado)
# La primera vez la caja pregunta si permite la depuración desde este PC: aceptar
# y marcar "Permitir siempre".
set -euo pipefail
IP=${1:?Uso: $0 <ip-de-la-caja>}
SDK="${ANDROID_HOME:-$HOME/android-sdk}"; ADB="$SDK/platform-tools/adb"
AQUI="$(cd "$(dirname "$0")" && pwd)"
APK="$AQUI/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || "$AQUI/empaquetar.sh"

echo "== conectando con $IP =="
"$ADB" connect "$IP:5555" | tail -1
"$ADB" -s "$IP:5555" wait-for-device
echo "   $("$ADB" -s "$IP:5555" shell getprop ro.product.model | tr -d '\r'), Android $("$ADB" -s "$IP:5555" shell getprop ro.build.version.release | tr -d '\r')"
echo "== instalando =="
"$ADB" -s "$IP:5555" install -r "$APK" | tail -1
echo "== lanzando =="
"$ADB" -s "$IP:5555" shell am start -n com.quattre.tv/.MainActivity >/dev/null
echo
echo "Registro de la app (Ctrl+C para salir). 'video:' es el reproductor, 'js:' la pagina."
"$ADB" -s "$IP:5555" logcat -c
"$ADB" -s "$IP:5555" logcat -s QuattreTV EventLogger | grep -vE "js: (APPEND|TRAS|FPS|VIDEO listo|CANAL)"
