#!/bin/bash
# Arranca un televisor Android TV emulado (1080p) e instala la app en el.
# Sirve para probar sin comprar ningun aparato. Necesita KVM (/dev/kvm).
#
#   android_app/emulador.sh          -> arranca (si no esta), instala y lanza la app
#   android_app/emulador.sh solo     -> solo arranca el emulador
#
# Teclas en la ventana del emulador: flechas y Enter son el mando; Esc es
# atras. Los botones de color y demas se mandan con adb, p. ej.:
#   adb shell input keyevent KEYCODE_PROG_RED
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_HOME:-$HOME/android-sdk}"
export ANDROID_HOME="$SDK"
export PATH="$SDK/platform-tools:$SDK/emulator:$SDK/cmdline-tools/latest/bin:$PATH"
API="${API:-36}"
AVD="QuattreTV_TV"
IMAGEN="system-images;android-$API;android-tv;x86_64"

if ! avdmanager list avd 2>/dev/null | grep -q "Name: $AVD"; then
    echo "== creando el televisor emulado $AVD =="
    echo no | avdmanager create avd -n "$AVD" -k "$IMAGEN" -d "tv_1080p" >/dev/null
    # GPU del PC de verdad (host). NUNCA swiftshader: pinta por software y el
    # 10/09/2026 dejo el PC colgado (rtkit: "canary thread starving").
    printf 'hw.ramSize=3072\nhw.gpu.enabled=yes\nhw.gpu.mode=host\ndisk.dataPartition.size=6G\n' >> "$HOME/.android/avd/$AVD.avd/config.ini"
fi

if ! adb devices | grep -q '^emulator-.*device$'; then
    echo "== arrancando el emulador (la primera vez tarda un par de minutos) =="
    # Restos de un cuelgue: con estos ficheros el emulador cree que ya esta en marcha.
    rm -f "$HOME/.android/avd/$AVD.avd"/hardware-qemu.ini.lock "$HOME/.android/avd/$AVD.avd"/multiinstance.lock
    # Tres cinturones, aprendidos a golpes (21-22/09/2026):
    #  - GPU host: la del PC. Por software (swiftshader) colgo el equipo entero.
    #  - taskset a 10 de 16 hilos + nice: el escritorio nunca se queda sin turno.
    #  - MemoryMax por cgroup: si se desmadra lo mata el sistema, no arrastra al PC.
    # Y -feature -HardwareDecoder: el "decodificador por hardware" del emulador
    # manda el H.264 al PC (ffmpeg por software, intenta CUDA y no hay) y
    # devuelve cada fotograma de 1080p al invitado: ese doble cruce hacia ir el
    # video a saltos (p90 100 ms/fotograma). Decodificando dentro: 25 fps clavados.
    # -scale 0.5 porque la ventana es de 1920x1080 y en un monitor 1080p no cabe.
    nohup systemd-run --user --scope -p MemoryMax=6G -p MemorySwapMax=512M \
        --description="Emulador Android TV $AVD" -- nice -n 10 taskset -c 0-9 \
        emulator -avd "$AVD" -gpu host -cores 8 -memory 2048 -no-snapshot -no-boot-anim \
        -scale "${ESCALA:-0.5}" -feature -HardwareDecoder ${EXTRA:-} \
        > "${TMPDIR:-/tmp}/quattretv-emulador.log" 2>&1 &
    adb wait-for-device
    until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
    echo "  arrancado"
fi

[ "${1:-}" = "solo" ] && exit 0

APK="$AQUI/app/build/outputs/apk/debug/app-debug.apk"
[ -f "$APK" ] || "$AQUI/empaquetar.sh"
echo "== instalando y lanzando =="
# Sin esto 'adb install' se queda colgado: Play Protect intenta verificar el APK en internet.
adb shell settings put global verifier_verify_adb_installs 0 >/dev/null 2>&1 || true
adb install -r "$APK" | tail -1
adb shell am start -n com.quattre.tv/.MainActivity >/dev/null
echo
echo "Registro de la app (lo que la pagina escribe por consola incluido):"
echo "  adb logcat -s QuattreTV"
