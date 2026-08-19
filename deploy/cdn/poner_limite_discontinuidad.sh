#!/bin/bash
set -e
UNIT=/etc/systemd/system/ffmpeg-hls@.service

echo "== copia de seguridad =="
cp -n "$UNIT" "$UNIT.bak-20260819" 2>/dev/null || true
ls -la "$UNIT.bak-20260819"

echo "== poniendo el limite por defecto para todos los canales =="
python3 - <<'PY'
p = '/etc/systemd/system/ffmpeg-hls@.service'
s = open(p).read()
if 'INOPTS' in s:
    print('  ya estaba puesto, no toco nada')
else:
    viejo = '    -i ${SRC} \\\n'
    assert s.count(viejo) == 1, 'no encuentro la linea del -i tal cual esperaba'
    # Por defecto 30 s. Un canal puede llevar la contraria poniendo INOPTS en su
    # fichero de /home/quattre/canales/.
    nuevo = '    ${INOPTS:--dts_delta_threshold 30} \\\n    -i ${SRC} \\\n'
    open(p, 'w').write(s.replace(viejo, nuevo))
    print('  anadido')
PY

echo "== como queda =="
grep -n 'INOPTS\|-i \${SRC}' "$UNIT"
systemd-analyze verify "$UNIT" 2>&1 | head -5 || true
