#!/bin/bash
# Instala o actualiza el escuchador de la EIT en cdn10 y cdn11 desde este PC
# (ver README). Toma la clave de iptv2 sin mostrarla. Para el escuchador de
# prueba de /tmp/eit, conserva su registro y deja el fijo en /home/quattre/eit
# con su entrada en el crontab de quattre.
set -e
cd "$(dirname "$0")"
TOKEN=$(ssh -p 12121 quattre@185.25.27.51 'grep "^EIT_TOKEN=" /var/www/quattretv/.env | cut -d= -f2-')
[ -n "$TOKEN" ] || { echo "No hay EIT_TOKEN en iptv2"; exit 1; }

for h in 185.25.27.53 185.25.27.54; do
    scp -q -P 12121 escucha.py quattre@$h:/tmp/escucha_nuevo.py
    printf '%s\n%s\n' "https://iptv2.quattre.com/api/v1/epg/eit/" "$TOKEN" | ssh -p 12121 quattre@$h '
        umask 077
        mkdir -p /home/quattre/eit
        cat > /home/quattre/eit/envio.conf
        mv /tmp/escucha_nuevo.py /home/quattre/eit/escucha.py
        cp -n /tmp/eit/cambios.log /home/quattre/eit/ 2>/dev/null || true
        cp -n /tmp/eit/canales.tsv /home/quattre/eit/ 2>/dev/null || true
        pkill -f "[e]scucha.py 86400" || true
        pkill -f "[e]scucha.py 315360000" || true
        (crontab -l 2>/dev/null | grep -v "escucha.py"
         echo "@reboot cd /home/quattre/eit && setsid nice -n 19 python3 escucha.py 315360000 >> escucha.out 2>&1 < /dev/null &"
         echo "*/5 * * * * pgrep -f \"[e]scucha.py 315360000\" >/dev/null || (cd /home/quattre/eit && setsid nice -n 19 python3 escucha.py 315360000 >> escucha.out 2>&1 < /dev/null &)"
        ) | crontab -
        echo "$(hostname): instalado"'
    ssh -n -f -p 12121 quattre@$h 'cd /home/quattre/eit && exec setsid nice -n 19 python3 escucha.py 315360000 >> escucha.out 2>&1 < /dev/null'
done
sleep 5
for h in 185.25.27.53 185.25.27.54; do
    ssh -p 12121 quattre@$h 'echo "$(hostname): $(ps -o etime=,args= -C python3 | grep "[e]scucha") | $(tail -1 /home/quattre/eit/escucha.out)"'
done
