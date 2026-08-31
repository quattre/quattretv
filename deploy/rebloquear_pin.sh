#!/bin/bash
# Vuelve a bloquear los canales de adultos AHORA, sin esperar los 30 minutos.
#
# Al acertar el PIN, el servidor deja una marca en la cache -- parental:<id de
# aparato> -- que dura media hora. Mientras esta puesta, los canales +18 se
# entregan con su direccion y no se vuelve a pedir nada. Esto la borra.
#
# Hace falta para probar el punto 23 del autochequeo de LG mas de una vez
# seguida: sin esto, entre intento e intento hay que esperar 30 minutos.
#
# Uso:
#   ./rebloquear_pin.sh            <- todos los aparatos de lgreview
#   ./rebloquear_pin.sh usuario    <- los de otro usuario
set -euo pipefail
USUARIO="${1:-lgreview}"
SERVIDOR="quattre@185.25.27.51"
PUERTO=12121

ssh -p "$PUERTO" -o StrictHostKeyChecking=no "$SERVIDOR" "
cd /var/www/quattretv && source venv/bin/activate 2>/dev/null
python manage.py shell -c \"
from django.core.cache import cache
from apps.accounts.models import User
u = User.objects.filter(username='$USUARIO').first()
if not u:
    print('  no existe el usuario $USUARIO')
else:
    n = 0
    for d in u.devices.all():
        clave = 'parental:%s' % d.id
        estaba = bool(cache.get(clave))
        cache.delete(clave)
        print('  %-20s %s' % (d.mac_address, 'estaba desbloqueado -> BLOQUEADO' if estaba else 'ya estaba bloqueado'))
        n += 1
    print('  %d aparatos de %s revisados' % (n, u.username))
\" 2>/dev/null | grep -v '^$'
"
