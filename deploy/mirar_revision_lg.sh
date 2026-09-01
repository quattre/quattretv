#!/bin/bash
# ¿Ha entrado ya el equipo de revision de LG?
#
# Mientras la app esta en QA no hay forma de saber desde el Seller Lounge cuando
# empiezan a probarla de verdad: el estado se queda en "QA Processing" desde que
# entra en la cola. Esto lo mira por el otro lado, en nuestro servidor.
#
# Dos señales, y hacen falta las dos:
#   - Peticiones desde las IP que LG entrego (deploy/ips_revision_lg.txt).
#   - Equipos nuevos dados de alta en la cuenta lgreview.
#
#   deploy/mirar_revision_lg.sh
set -uo pipefail
SERVIDOR="quattre@185.25.27.51"
PUERTO=12121

ssh -p "$PUERTO" -o StrictHostKeyChecking=no "$SERVIDOR" '
PREF="^1\.222\.94\.|^27\.122\.242\.|^112\.219\.71\.|^115\.114\.17\.|^116\.120\.157\.|^121\.66\.144\.|^182\.224\.177\.|^195\.160\.253\.|^203\.247\.149\.|^217\.79\.6\.|^222\.112\.209\.|^49\.172\.166\."
LOGS=$(ls /var/log/nginx/*access*.log 2>/dev/null)

echo "== Peticiones desde las IP de revision de LG =="
N=$(cat $LOGS 2>/dev/null | grep -cE "$PREF")
if [ "${N:-0}" -eq 0 ]; then
  echo "   ninguna todavia"
else
  echo "   $N peticiones. Las ultimas:"
  cat $LOGS 2>/dev/null | grep -E "$PREF" | tail -8 | sed "s/^/     /"
  echo
  echo "   desde que IP:"
  cat $LOGS 2>/dev/null | grep -E "$PREF" | awk "{print \$1}" | sort | uniq -c | sort -rn | sed "s/^/     /"
fi

echo
cd /var/www/quattretv && source venv/bin/activate 2>/dev/null
python manage.py shell -c "
from apps.accounts.models import User
from django.utils import timezone
u = User.objects.get(username=\"lgreview\")
ahora = timezone.now()
print(\"== Equipos de la cuenta de revision (%d de %s) ==\" % (u.devices.count(), u.limite_equipos))
for d in u.devices.all().order_by(\"-last_seen\"):
    if d.last_seen:
        m = (ahora - d.last_seen).total_seconds() / 60
        cuando = (\"hace %.0f min\" % m) if m < 180 else (\"hace %.1f h\" % (m / 60))
    else:
        cuando = \"nunca\"
    nuestro = \" (nuestro)\" if (d.last_ip or \"\").startswith(\"185.25.27.\") else \"\"
    print(\"   %-18s ip=%-16s %s%s\" % (d.mac_address, d.last_ip or \"-\", cuando, nuestro))
" 2>/dev/null | grep -v "^$"
'
