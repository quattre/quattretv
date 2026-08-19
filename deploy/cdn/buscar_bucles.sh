#!/bin/bash
# Busca la firma del bucle: mismo valor con signo + y signo -, y que NO sea la
# vuelta a cero del reloj (95443xxxxxx). Cuenta cuantas veces y en cuanto tiempo.
for u in $(systemctl list-units 'ffmpeg-hls@*' --no-legend --plain 2>/dev/null | awk '{print $1}'); do
  c=${u#ffmpeg-hls@}; c=${c%.service}
  journalctl -u "$u" --no-pager -n 2000 2>/dev/null | grep discontinuity > /tmp/_d.txt || true
  [ -s /tmp/_d.txt ] || continue
  # magnitudes que aparecen con los dos signos y no son la vuelta a cero
  mags=$(grep -o '): -\?[0-9]*' /tmp/_d.txt | grep -o '\-\?[0-9]*$' | sort -u)
  sospechosas=""
  for m in $mags; do
    [ "${m#-}" = "$m" ] || continue
    [ ${#m} -ge 11 ] && continue
    if grep -q "): $m," /tmp/_d.txt && grep -q "): -$m," /tmp/_d.txt; then
      n=$(grep -c ": -\?$m," /tmp/_d.txt)
      seg=$(awk -v m="$m" 'BEGIN{printf "%.2f", m/1000000}')
      sospechosas="$sospechosas ${seg}s(x$n)"
    fi
  done
  if [ -n "$sospechosas" ]; then
    pri=$(head -1 /tmp/_d.txt | awk '{print $1" "$2" "$3}')
    ult=$(tail -1 /tmp/_d.txt | awk '{print $1" "$2" "$3}')
    printf '  %-22s BUCLE:%s   [%s -> %s]\n' "$c" "$sospechosas" "$pri" "$ult"
  fi
done
rm -f /tmp/_d.txt
