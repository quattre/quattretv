#!/bin/bash
# Anade a check_hls.sh la comprobacion que le falta: el bucle de correcciones de
# tiempo en la ENTRADA.
#
# El script ya comprueba discontinuidades (su comprobacion nº 3), pero las busca
# en la SALIDA: lanza ffmpeg contra el index.m3u8 y cuenta lineas. Cuando ffmpeg
# se queda atascado corrigiendo un salto desigual, la salida sigue siendo
# impecable — medido: -0,040 s clavados entre audio y video, sin huecos — asi que
# por ahi no se ve nada. El unico rastro esta en el registro del propio canal.
#
# Ver README.md para el diagnostico completo.
set -e

SCRIPT=/usr/local/bin/check_hls.sh
[ -f "$SCRIPT" ] || { echo "No encuentro $SCRIPT"; exit 1; }

echo "== copia de seguridad =="
cp -n "$SCRIPT" "$SCRIPT.bak-20260819" 2>/dev/null || true
ls -la "$SCRIPT.bak-20260819"

echo "== www-data necesita poder leer el registro =="
# Por defecto no esta en ningun grupo extra, asi que journalctl no le deja ver
# las unidades de los canales y la comprobacion nueva daria 0 siempre.
if id -nG www-data | tr ' ' '\n' | grep -qx systemd-journal; then
    echo "  ya estaba en systemd-journal"
else
    usermod -aG systemd-journal www-data
    echo "  anadido a systemd-journal (hace falta reiniciar check-hls)"
fi

echo "== anadiendo la comprobacion =="
python3 - <<'PY'
p = '/usr/local/bin/check_hls.sh'
s = open(p).read()

if 'timestamp discontinuity' in s:
    print('  ya estaba puesta, no toco nada')
    raise SystemExit(0)

ancla = '''    # 4. tamaño
'''
assert s.count(ancla) == 1, 'ABORTADO: el script no es el esperado'

nueva = '''    # 3.b bucle de correcciones de tiempo en la ENTRADA
    # ffmpeg lleva una sola correccion para todo el fichero de entrada. Si le
    # llega un salto que afecta solo a una de las pistas y pasa de 10 s, corrige
    # el video y descuadra el audio, corrige el audio y descuadra el video, sin
    # salir nunca. La emision sigue saliendo bien — por eso la comprobacion 3,
    # que mira la salida, no lo ve — pero el sonido se descoloca. Solo se
    # arregla reiniciando. Un canal sano saca unos pocos avisos cada 26,5 h
    # (la vuelta a cero del reloj); uno atascado saca cientos por minuto.
    bucle=$(journalctl -u "ffmpeg-hls@$canal.service" --since "2 min ago" --no-pager 2>/dev/null | grep -c "timestamp discontinuity")
    if [ "${bucle:-0}" -gt 60 ]; then
        if [ "$silent" != "silent" ]; then
            notify "$canal" "AUDIO DESCOLOCADO: bucle de correcciones ($bucle avisos en 2 min)" "⚠️"
        fi
        sudo /bin/systemctl restart "ffmpeg-hls@$canal.service"
        return 1
    else
        echo "   ✔ Correcciones de tiempo: ${bucle:-0} en 2 min"
    fi

'''

open(p, 'w').write(s.replace(ancla, nueva + ancla))
print('  anadida')
PY

echo "== el token de Telegram estaba a la vista de cualquiera =="
# -rwxr-xr-x: cualquiera con una shell en la maquina podia leer el token del bot
# y escribir en el grupo. El script lo lanza systemd como www-data, que es el
# dueno, asi que no necesita permiso de lectura para los demas.
chmod 750 "$SCRIPT"
ls -la "$SCRIPT"

echo "== comprobando que no he roto la sintaxis =="
bash -n "$SCRIPT" && echo "  sintaxis correcta"

echo
echo "Ahora hay que reiniciar el vigilante para que coja el grupo nuevo:"
echo "    sudo systemctl restart check-hls"
