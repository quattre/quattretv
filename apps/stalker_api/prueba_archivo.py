"""Comprueba que un canal solo anuncia archivo si hay un grabador dando señales.

El fallo que cierra: 81 canales anunciaban `archive: 1` con el archivo sin
conectar, asi que pulsar sobre un programa ya emitido acababa en "Archivo no
disponible". Se anunciaba mirando solo el canal, sin comprobar el grabador.
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
from apps.pvr.models import StorageServer, StorageRole
import json

# --- limpieza de restos de una pasada anterior ---
Device.objects.filter(uid__startswith='ARCHIVO').delete()
User.objects.filter(username='t_archivo').delete()
Tariff.objects.filter(name='TEST archivo').delete()
StorageServer.objects.filter(name='TEST storage').delete()
Channel.objects.filter(name='TEST canal archivo').delete()

fallos = []


def comprobar(descripcion, obtenido, esperado):
    if obtenido == esperado:
        print('  OK   %s' % descripcion)
    else:
        fallos.append(descripcion)
        print('  MAL  %s: esperaba %r y ha salido %r' % (descripcion, esperado, obtenido))


t = Tariff.objects.create(name='TEST archivo', max_devices=2, max_concurrent_streams=2,
                          has_catchup=True)
u = User.objects.create_user(username='t_archivo', password='clave')
u.tariff = t
u.save()

# Un canal que cumple TODO lo que dependia del propio canal: catchup activado y
# un multicast del que grabarlo. Antes, con esto bastaba para anunciar archivo.
canal = Channel.objects.create(
    name='TEST canal archivo',
    number=99001,
    stream_url='http://ejemplo/hls/prueba/index.m3u8',
    multicast_url='udp://239.0.0.1:1234',
    has_catchup=True,
    is_active=True,
)

c = Client()
r = c.get('/quattretv/stb/portal.php?type=stb&action=login&login=t_archivo'
          '&password=clave&device_uid=ARCHIVO01&device_type=lg')
if r.status_code != 200:
    raise SystemExit('el login ha respondido %s: %s' % (r.status_code, r.content[:200]))


def archivo_del_canal():
    """Lo que el deco recibe para nuestro canal de prueba."""
    cache.delete('archivo:en_marcha')   # que no conteste la respuesta cacheada
    pagina = 0
    while True:
        resp = c.get('/quattretv/stb/portal.php?type=itv&action=get_ordered_list&p=%d' % pagina)
        js = json.loads(resp.content)['js']
        for fila in js['data']:
            if fila['name'] == 'TEST canal archivo':
                return fila['archive']
        if (pagina + 1) * js['max_page_items'] >= js['total_items']:
            raise SystemExit('el canal de prueba no aparece en la lista')
        pagina += 1


print('1. Sin ningun grabador dado de alta')
StorageServer.objects.filter(role__in=[StorageRole.ARCHIVE, StorageRole.BOTH]).update(last_sync=None)
comprobar('no se anuncia archivo', archivo_del_canal(), 0)

print('2. Grabador dado de alta pero que nunca ha pedido tareas')
s = StorageServer.objects.create(
    name='TEST storage', role=StorageRole.ARCHIVE,
    api_url='http://192.168.100.51/storage/', is_active=True, last_sync=None,
)
comprobar('sigue sin anunciarse', archivo_del_canal(), 0)

print('3. Grabador que pidio tareas hace media hora (esta parado)')
s.last_sync = timezone.now() - timedelta(minutes=30)
s.save(update_fields=['last_sync'])
comprobar('sigue sin anunciarse', archivo_del_canal(), 0)

print('4. Grabador que acaba de pedir tareas')
s.last_sync = timezone.now()
s.save(update_fields=['last_sync'])
comprobar('ahora si se anuncia', archivo_del_canal(), 1)

print('5. Grabador vivo pero desactivado a mano')
s.is_active = False
s.save(update_fields=['is_active'])
comprobar('no se anuncia', archivo_del_canal(), 0)

print('6. Pedir el archivo directamente cuando no lo hay')
s.is_active = True
s.last_sync = None
s.save(update_fields=['is_active', 'last_sync'])
cache.delete('archivo:en_marcha')
resp = c.get('/quattretv/stb/portal.php?type=tv_archive&action=create_link'
             '&ch_id=%d&utc=%d' % (canal.id, int(timezone.now().timestamp()) - 3600))
js = json.loads(resp.content)['js']
comprobar('se responde con un error, no con una URL', 'cmd' in js, False)
print('     respuesta: %s' % js.get('error'))

# --- limpieza ---
Device.objects.filter(uid__startswith='ARCHIVO').delete()
User.objects.filter(username='t_archivo').delete()
Tariff.objects.filter(name='TEST archivo').delete()
StorageServer.objects.filter(name='TEST storage').delete()
Channel.objects.filter(name='TEST canal archivo').delete()
cache.delete('archivo:en_marcha')

print()
if fallos:
    raise SystemExit('FALLAN %d comprobaciones: %s' % (len(fallos), ', '.join(fallos)))
print('Las 6 comprobaciones pasan.')
