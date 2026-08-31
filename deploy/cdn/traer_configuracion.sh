#!/bin/bash
# Trae a este repositorio la configuracion que hay AHORA en los dos CDN.
#
# Es solo lectura: no toca nada en las maquinas. Sirve para tener en git lo que
# de verdad esta corriendo, que hasta ahora vivia unicamente en los servidores y
# no habia forma de saber que habia cambiado ni cuando.
#
#   deploy/cdn/traer_configuracion.sh
#
# Despues, un 'git diff' enseña lo que se movio desde la ultima vez.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
PUERTO=12121

traer() {
  local nombre=$1 ip=$2
  local destino="$AQUI/$nombre"
  mkdir -p "$destino/canales"
  rm -f "$destino/canales"/* 2>/dev/null || true

  scp -q -P "$PUERTO" -o StrictHostKeyChecking=no \
      "quattre@$ip:/etc/systemd/system/ffmpeg-hls@.service" "$destino/"
  scp -q -P "$PUERTO" -o StrictHostKeyChecking=no \
      "quattre@$ip:/etc/nginx/conf.d/hls.conf" \
      "quattre@$ip:/etc/nginx/conf.d/hls-ssl.conf" "$destino/" 2>/dev/null || true
  scp -q -P "$PUERTO" -o StrictHostKeyChecking=no \
      "quattre@$ip:/home/quattre/canales/*" "$destino/canales/"

  # limpiar_canal.sh deja una copia de seguridad al lado cada vez que toca un
  # canal, y ahi se quedan. No molestan a systemd -- ninguna unidad las usa --
  # pero aqui solo interesa la configuracion que esta viva.
  find "$destino/canales" -name '*.bak*' -o -name '*.antes-*' | while read -r f; do
      rm -f "$f"
  done

  echo "  $nombre: $(ls -1 "$destino/canales" | wc -l) canales"
}

traer cdn10 185.25.27.53
traer cdn11 185.25.27.54

echo
echo "Listo. 'git diff deploy/cdn' enseña lo que ha cambiado desde la ultima vez."
