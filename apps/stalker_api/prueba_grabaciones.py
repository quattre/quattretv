"""Comprueba que no se ofrece grabar si no hay un grabador que conteste.

El fallo que cierra: el portal decia "Grabacion programada" con el grabador sin
conectar. La comprobacion del servidor miraba que el grabador estuviera dado de
alta — y record1b lo esta, para poder vigilarlo desde el panel — pero no que
respondiera.

Aqui no vale el truco del archivo (mirar last_sync) porque el grabador de
clientes no viene a pedir tareas, recibe ordenes: su last_sync es nulo aunque
funcione. Por eso se le pregunta, y por eso estas pruebas sustituyen la llamada
de red en vez de depender de que haya o no un grabador de verdad al otro lado.
"""
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from django.test import Client
from django.conf import settings
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
from apps.accounts.models import User, Tariff
from apps.channels.models import Channel
from apps.devices.models import Device
from apps.epg.models import Program
from apps.pvr.models import Recording, StorageServer, StorageRole
import json

# --- limpieza de restos ---
Device.objects.filter(uid__startswith='GRABA').delete()
Recording.objects.filter(title='TEST programa grabable').delete()
Program.objects.filter(title='TEST programa grabable').delete()
Channel.objects.filter(name='TEST canal grabable').delete()
User.objects.filter(username='t_graba').delete()
Tariff.objects.filter(name='TEST grabaciones').delete()
StorageServer.objects.filter(name='TEST grabador').delete()

fallos = []


def comprobar(descripcion, obtenido, esperado):
    if obtenido == esperado:
        print('  OK   %s' % descripcion)
    else:
        fallos.append(descripcion)
        print('  MAL  %s: esperaba %r y ha salido %r' % (descripcion, esperado, obtenido))


t = Tariff.objects.create(name='TEST grabaciones', max_devices=2,
                          max_concurrent_streams=2, has_pvr=True)
u = User.objects.create_user(username='t_graba', password='clave')
u.tariff = t
u.save()

canal = Channel.objects.create(
    name='TEST canal grabable', number=99002,
    stream_url='http://ejemplo/hls/prueba/index.m3u8',
    multicast_url='udp://239.0.0.2:1234', is_active=True,
)
programa = Program.objects.create(
    channel=canal, title='TEST programa grabable',
    start_time=timezone.now() + timedelta(hours=1),
    end_time=timezone.now() + timedelta(hours=2),
)
grabador = StorageServer.objects.create(
    name='TEST grabador', role=StorageRole.RECORDS,
    api_url='http://192.168.100.52/storage/', is_active=True, last_sync=None,
)

c = Client()
r = c.get('/quattretv/stb/portal.php?type=stb&action=login&login=t_graba'
          '&password=clave&device_uid=GRABA01&device_type=lg')
if r.status_code != 200:
    raise SystemExit('el login ha respondido %s: %s' % (r.status_code, r.content[:200]))


# --- se sustituye la llamada de red al grabador ---
class RespuestaFalsa:
    def __init__(self, codigo):
        self.status_code = codigo


def grabador_contesta(codigo):
    def falsa(*args, **kwargs):
        return RespuestaFalsa(codigo)
    import requests
    requests.get = falsa
    cache.delete('grabador:responde')


def grabador_no_contesta():
    def falsa(*args, **kwargs):
        raise OSError('no hay ruta hasta el grabador')
    import requests
    requests.get = falsa
    cache.delete('grabador:responde')


import requests
guardado = requests.get


def modulos():
    resp = c.get('/quattretv/stb/portal.php?type=stb&action=get_modules')
    return json.loads(resp.content)['js']['result']['all_modules']


def programar():
    resp = c.get('/quattretv/stb/portal.php?type=pvr&action=create_task&program_id=%d'
                 % programa.id)
    return json.loads(resp.content)['js']


try:
    print('1. El grabador esta dado de alta pero no contesta')
    grabador_no_contesta()
    comprobar('las grabaciones no salen en el menu', 'records' in modulos(), False)
    js = programar()
    comprobar('programar devuelve error', js.get('result'), None)
    print('     respuesta: %s' % js.get('error'))
    comprobar('no se ha creado ninguna grabacion',
              Recording.objects.filter(program=programa).count(), 0)

    print('2. El grabador contesta (aunque sea pidiendo credenciales)')
    grabador_contesta(401)
    comprobar('las grabaciones salen en el menu', 'records' in modulos(), True)
    js = programar()
    comprobar('programar funciona', js.get('result'), True)
    comprobar('se ha creado la grabacion',
              Recording.objects.filter(program=programa).count(), 1)

    print('3. Con el grabador contestando pero sin PVR en la tarifa')
    Recording.objects.filter(program=programa).delete()
    t.has_pvr = False
    t.save(update_fields=['has_pvr'])
    cache.delete('grabador:responde')
    comprobar('las grabaciones no salen en el menu', 'records' in modulos(), False)
    js = programar()
    comprobar('programar devuelve error', js.get('result'), None)
    print('     respuesta: %s' % js.get('error'))

    print('4. El resultado se cachea, no se llama al grabador en cada pulsacion')
    t.has_pvr = True
    t.save(update_fields=['has_pvr'])
    llamadas = {'n': 0}

    def contando(*args, **kwargs):
        llamadas['n'] += 1
        return RespuestaFalsa(401)

    requests.get = contando
    cache.delete('grabador:responde')
    for _ in range(5):
        modulos()
    comprobar('cinco peticiones, una sola llamada al grabador', llamadas['n'], 1)

finally:
    requests.get = guardado
    cache.delete('grabador:responde')
    Recording.objects.filter(program=programa).delete()
    Device.objects.filter(uid__startswith='GRABA').delete()
    Program.objects.filter(title='TEST programa grabable').delete()
    Channel.objects.filter(name='TEST canal grabable').delete()
    User.objects.filter(username='t_graba').delete()
    Tariff.objects.filter(name='TEST grabaciones').delete()
    StorageServer.objects.filter(name='TEST grabador').delete()

print()
if fallos:
    raise SystemExit('FALLAN %d comprobaciones: %s' % (len(fallos), ', '.join(fallos)))
print('Las comprobaciones pasan.')
