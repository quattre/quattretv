"""Comprueba que un equipo fantasma libera su plaza y uno en uso no."""
from datetime import timedelta
from django.utils import timezone
from django.test import Client
from django.test.utils import override_settings
from django.conf import settings
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
from apps.accounts.models import User, Tariff
from apps.devices.models import Device
import json

Device.objects.filter(uid__startswith='FANTASMA').delete()
User.objects.filter(username='t_fantasma').delete()
Tariff.objects.filter(name='TEST fantasmas').delete()

t = Tariff.objects.create(name='TEST fantasmas', max_devices=2, max_concurrent_streams=2)
u = User.objects.create_user(username='t_fantasma', password='clave'); u.tariff = t; u.save()
c = Client()

def entrar(uid):
    r = c.get('/quattretv/stb/portal.php?type=stb&action=login&login=t_fantasma'
              '&password=clave&device_uid=%s&device_type=lg' % uid)
    if r.status_code != 200:
        raise SystemExit('respuesta %s: %s' % (r.status_code, r.content[:200]))
    return json.loads(r.content)['js']

fallos = []
def check(t_, cond, extra=''):
    print(('  OK  ' if cond else ' FALLO ') + t_ + (' -> %s' % extra if extra else ''))
    if not cond: fallos.append(t_)

print('\n== Se llenan las dos plazas ==')
a = entrar('FANTASMA-1'); b = entrar('FANTASMA-2')
check('entran los dos', 'mac' in a and 'mac' in b)
check('hay dos equipos', u.devices.filter(is_active=True).count() == 2)

print('\n== Un tercero, con las dos plazas en uso, se rechaza ==')
tercero = entrar('FANTASMA-3')
check('lo rechaza', 'error' in tercero, tercero.get('error', '')[:50])

print('\n== Ahora uno de los dos se vuelve fantasma (100 dias sin aparecer) ==')
d1 = Device.objects.get(uid='FANTASMA-1')
d1.last_seen = timezone.now() - timedelta(days=100); d1.save(update_fields=['last_seen'])
cuarto = entrar('FANTASMA-4')
check('ahora si deja entrar al nuevo', 'mac' in cuarto, cuarto)
check('el fantasma se ha retirado', not Device.objects.get(uid='FANTASMA-1').is_active)
check('el que si se usaba sigue activo', Device.objects.get(uid='FANTASMA-2').is_active)
check('siguen siendo dos activos', u.devices.filter(is_active=True).count() == 2)

print('\n== Un equipo usado hace 80 dias NO se toca ==')
d2 = Device.objects.get(uid='FANTASMA-2')
d2.last_seen = timezone.now() - timedelta(days=80); d2.save(update_fields=['last_seen'])
quinto = entrar('FANTASMA-5')
check('no lo deja entrar', 'error' in quinto, quinto.get('error','')[:40])
check('el de 80 dias sigue activo', Device.objects.get(uid='FANTASMA-2').is_active)

Device.objects.filter(uid__startswith='FANTASMA').delete()
User.objects.filter(username='t_fantasma').delete()
Tariff.objects.filter(name='TEST fantasmas').delete()
print('\n' + ('TODO CORRECTO' if not fallos else 'FALLOS: ' + ', '.join(fallos)))
