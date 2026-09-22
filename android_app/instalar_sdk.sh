#!/bin/bash
# Instala el SDK de Android en ~/android-sdk, sin Android Studio: solo las
# herramientas de consola, igual que se hizo con Tizen Studio para Samsung.
#
# Deja instalado lo justo para compilar la app y para probarla en el emulador
# de Android TV:
#   - platform-tools (adb)
#   - la plataforma y las build-tools de la version a la que apunta la app
#   - el emulador y una imagen de Android TV
#
# Se puede volver a ejecutar sin miedo: lo que ya esta, se lo salta.
#
#   android_app/instalar_sdk.sh
set -euo pipefail

SDK="${ANDROID_HOME:-$HOME/android-sdk}"
API="${API:-36}"
IMAGEN="${IMAGEN:-system-images;android-$API;android-tv;x86_64}"

mkdir -p "$SDK/cmdline-tools"
cd "$SDK"

if [ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
    echo "== descargando las herramientas de consola =="
    # El nombre del zip cambia con cada version; se saca de la pagina oficial.
    ZIP="$(curl -sL https://developer.android.com/studio \
           | grep -oE 'commandlinetools-linux-[0-9]+_latest\.zip' | head -1)"
    [ -n "$ZIP" ] || { echo "No encuentro el zip de las command line tools"; exit 1; }
    curl -# -L -o /tmp/cmdline-tools.zip "https://dl.google.com/android/repository/$ZIP"
    rm -rf "$SDK/cmdline-tools/latest" /tmp/cmdline-tools-x
    mkdir -p /tmp/cmdline-tools-x
    unzip -q /tmp/cmdline-tools.zip -d /tmp/cmdline-tools-x
    mv /tmp/cmdline-tools-x/cmdline-tools "$SDK/cmdline-tools/latest"
    rm -rf /tmp/cmdline-tools.zip /tmp/cmdline-tools-x
fi

SDKMANAGER="$SDK/cmdline-tools/latest/bin/sdkmanager"

echo "== aceptando licencias =="
yes | "$SDKMANAGER" --licenses >/dev/null 2>&1 || true

echo "== instalando paquetes (tarda: son unos 2 GB) =="
"$SDKMANAGER" --install \
    "platform-tools" \
    "platforms;android-$API" \
    "build-tools;$API.0.0" \
    "emulator" \
    "$IMAGEN"

# Para compilar hace falta un JDK 17 con javac. El java del sistema es solo
# el JRE, el de Tizen Studio es un 8 y el de Android Studio (snap) es
# demasiado nuevo para este Gradle. Se baja un Temurin 17 y se deja aqui.
if [ ! -x "$SDK/jdk-17/bin/javac" ]; then
    echo "== descargando el JDK 17 (Temurin) =="
    curl -# -L -o /tmp/jdk17.tar.gz \
        "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse?project=jdk"
    rm -rf "$SDK/jdk-17" /tmp/jdk17-x; mkdir -p /tmp/jdk17-x
    tar -xzf /tmp/jdk17.tar.gz -C /tmp/jdk17-x
    mv /tmp/jdk17-x/jdk-17* "$SDK/jdk-17"
    rm -rf /tmp/jdk17.tar.gz /tmp/jdk17-x
fi

echo
echo "SDK instalado en $SDK"
echo "Añade a tu entorno (o usalo desde los scripts, que ya lo hacen):"
echo "  export ANDROID_HOME=$SDK"
echo "  export PATH=\$PATH:$SDK/platform-tools:$SDK/emulator"
