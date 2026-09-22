#!/bin/bash
# Prepara y compila la app de Android TV.
#
# El cargador y el splash NO se duplican aqui: se toman de lg_app, igual que
# hace la app de Samsung. Dos copias del mismo fichero acaban separandose sin
# que nadie se de cuenta. Los iconos y el banner de la tienda se generan a
# partir de los graficos de lg_app cada vez.
#
#   android_app/empaquetar.sh            -> APK de pruebas (debug), para el emulador
#   android_app/empaquetar.sh tienda     -> ademas el .aab firmado para Google Play
#                                           (crea la clave de subida si no existe)
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/.." && pwd)"
SDK="${ANDROID_HOME:-$HOME/android-sdk}"
GRADLE="$(command -v gradle || echo "$SDK/gradle-8.11.1/bin/gradle")"
MODO="${1:-pruebas}"

[ -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ] || { echo "Falta el SDK: android_app/instalar_sdk.sh"; exit 1; }
if [ ! -x "$GRADLE" ]; then
    echo "== descargando Gradle 8.11.1 =="
    (cd "$SDK" && curl -sL -o g.zip https://services.gradle.org/distributions/gradle-8.11.1-bin.zip && unzip -q g.zip && rm g.zip)
fi
export ANDROID_HOME="$SDK"

# Hace falta un JDK 17 con javac: el que deja instalar_sdk.sh en el SDK. El
# java del sistema es solo el JRE, y ni el de Tizen Studio (8) ni el de
# Android Studio (demasiado nuevo para este Gradle) valen.
if [ -z "${JAVA_HOME:-}" ] || [ ! -x "$JAVA_HOME/bin/javac" ]; then
    export JAVA_HOME="$SDK/jdk-17"
fi
[ -x "$JAVA_HOME/bin/javac" ] || { echo "Falta el JDK 17: android_app/instalar_sdk.sh"; exit 1; }

echo "== copiando el cargador y el splash de lg_app =="
ASSETS="$AQUI/app/src/main/assets"
rm -rf "$ASSETS"; mkdir -p "$ASSETS"
cp "$RAIZ/lg_app/index.html" "$RAIZ/lg_app/splash.png" "$ASSETS/"

echo "== generando iconos y banner =="
python3 - "$RAIZ/lg_app" "$AQUI/app/src/main/res" <<'PY'
import sys, os
from PIL import Image
origen, res = sys.argv[1], sys.argv[2]

# Icono de la app: el mismo de la tienda de LG, a los cinco tamaños de Android.
icono = Image.open(os.path.join(origen, 'icon_tienda_400.png')).convert('RGB')
for carpeta, px in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)]:
    d = os.path.join(res, 'mipmap-' + carpeta); os.makedirs(d, exist_ok=True)
    icono.resize((px, px), Image.LANCZOS).save(os.path.join(d, 'ic_launcher.png'))

# Banner del lanzador de Android TV: 320x180 obligatorio (xhdpi). Es el
# recorte central del splash, donde esta el logotipo, encogido.
splash = Image.open(os.path.join(origen, 'splash.png')).convert('RGB')
w, h = splash.size
banner = splash.crop((w // 2 - 480, h // 2 - 270, w // 2 + 480, h // 2 + 270)).resize((320, 180), Image.LANCZOS)
d = os.path.join(res, 'drawable-xhdpi'); os.makedirs(d, exist_ok=True)
banner.save(os.path.join(d, 'tv_banner.png'))
print('  iconos 48-192 px y banner 320x180 generados')
PY

if [ "$MODO" = "tienda" ]; then
    CLAVES="$HOME/android-keys"
    JKS="$CLAVES/quattretv-upload.jks"
    PROPS="$CLAVES/quattretv-upload.properties"
    if [ ! -f "$JKS" ]; then
        echo "== creando la clave de subida a Google Play (una sola vez) =="
        mkdir -p "$CLAVES"; chmod 700 "$CLAVES"
        PASS="$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 24)"
        keytool -genkeypair -v -keystore "$JKS" -alias upload -keyalg RSA -keysize 2048 \
            -validity 10000 -storepass "$PASS" -keypass "$PASS" \
            -dname "CN=QuattreTV, O=Quattre Internet SL, L=Valencia, C=ES" >/dev/null 2>&1
        printf 'storePassword=%s\nkeyPassword=%s\nkeyAlias=upload\n' "$PASS" "$PASS" > "$PROPS"
        chmod 600 "$JKS" "$PROPS"
        echo "  clave en $JKS (contraseña en $PROPS). HAZ COPIA: sin ella no se"
        echo "  puede actualizar la app. Google Play permite pedir otra, pero es un tramite."
    fi
fi

echo "== compilando =="
cd "$AQUI"
if [ "$MODO" = "tienda" ]; then
    "$GRADLE" -q assembleDebug bundleRelease assembleRelease
else
    "$GRADLE" -q assembleDebug
fi

echo
echo "== resultado =="
for f in app/build/outputs/apk/debug/app-debug.apk app/build/outputs/apk/release/app-release.apk app/build/outputs/bundle/release/app-release.aab; do
    [ -f "$f" ] && printf "  %8s  %s\n" "$(du -h "$f" | cut -f1)" "$f"
done
echo
echo "Para probarlo en el emulador de Android TV:  android_app/emulador.sh"
echo "Para un televisor real con depuracion activada: adb connect <ip> && adb install -r app/build/outputs/apk/debug/app-debug.apk"
