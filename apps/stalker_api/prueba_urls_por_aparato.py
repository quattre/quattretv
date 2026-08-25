"""Cada aparato recibe la direccion del canal que sabe reproducir.

El fallo que cierra: al pasar los canales a https para que la television de LG
pudiera verlos, los decos MAG se quedaron sin imagen. Llevaban años pidiendo el
puerto 1500 en claro y su TLS es antiguo.

El CDN sirve las dos puertas a la vez desde el mismo sitio, asi que no hay que
elegir: se le da a cada uno la suya.
"""
from django.test import Client
from django.conf import settings
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
from apps.accounts.models import User, Tariff
from apps.channels.models import Channel
from apps.devices.models import Device
from apps.stalker_api.views import url_para_dispositivo
import json

Device.objects.filter(uid__startswith='URLS').delete()
User.objects.filter(username='t_urls').delete()
Tariff.objects.filter(name='TEST urls').delete()
Channel.objects.filter(name='TEST canal urls').delete()

fallos = []


def comprobar(descripcion, obtenido, esperado):
    if obtenido == esperado:
        print('  OK   %s' % descripcion)
    else:
        fallos.append(descripcion)
        print('  MAL  %s:\n         esperaba %r\n         ha salido %r'
              % (descripcion, esperado, obtenido))


t = Tariff.objects.create(name='TEST urls', max_devices=5, max_concurrent_streams=3)
u = User.objects.create_user(username='t_urls', password='clave')
u.tariff = t
u.save()

HTTPS = 'https://cdn10.quattre.com/hls/la1/index.m3u8'
HTTP1500 = 'http://cdn10.quattre.com:1500/hls/la1/index.m3u8'

canal = Channel.objects.create(
    name='TEST canal urls', number=99003, stream_url=HTTPS, is_active=True,
)


def aparato(uid, tipo):
    c = Client()
    r = c.get('/quattretv/stb/portal.php?type=stb&action=login&login=t_urls'
              '&password=clave&device_uid=%s&device_type=%s' % (uid, tipo))
    if r.status_code != 200:
        raise SystemExit('login %s: %s' % (r.status_code, r.content[:200]))
    c.cookies['mac'] = json.loads(r.content)['js']['mac']
    return c


print('1. La funcion, tipo por tipo')
for tipo, esperado, quien in [
    ('lg', HTTPS, 'la television de LG'),
    ('samsung', HTTPS, 'una Samsung'),
    ('web', HTTPS, 'un navegador'),
    ('smart_tv', HTTPS, 'otra smart TV'),
    ('mag', HTTP1500, 'un deco MAG'),
    ('android', HTTP1500, 'un Android'),
]:
    d = Device(device_type=tipo)
    comprobar('%s recibe %s' % (quien, 'https' if esperado == HTTPS else 'el 1500'),
              url_para_dispositivo(HTTPS, d), esperado)

print('2. Casos raros que no deben romper nada')
comprobar('sin aparato se deja como esta', url_para_dispositivo(HTTPS, None), HTTPS)
comprobar('una url vacia sigue vacia', url_para_dispositivo('', Device(device_type='mag')), '')
comprobar('una url que ya iba en http no se toca',
          url_para_dispositivo(HTTP1500, Device(device_type='mag')), HTTP1500)
comprobar('una url de otro sitio no se toca',
          url_para_dispositivo('https://otra.cosa/algo.m3u8?x=1', Device(device_type='lg')),
          'https://otra.cosa/algo.m3u8?x=1')

print('3. Por el camino de verdad: lo que recibe cada aparato en la lista')
for tipo, esperado in [('lg', 'https'), ('mag', 'http')]:
    c = aparato('URLS_' + tipo, tipo)
    datos = json.loads(c.get(
        '/quattretv/stb/portal.php?type=itv&action=get_ordered_list&p=0').content)['js']['data']
    fila = [x for x in datos if x['name'] == 'TEST canal urls']
    if not fila:
        # El canal de prueba puede caer en otra pagina si hay muchos canales.
        pagina = 1
        while not fila and pagina < 6:
            datos = json.loads(c.get(
                '/quattretv/stb/portal.php?type=itv&action=get_ordered_list&p=%d'
                % pagina).content)['js']['data']
            fila = [x for x in datos if x['name'] == 'TEST canal urls']
            pagina += 1
    comprobar('en la lista, un %s recibe %s' % (tipo, esperado),
              fila[0]['cmd'].split(':')[0] if fila else 'no aparece', esperado)

    enlace = json.loads(c.get(
        '/quattretv/stb/portal.php?type=itv&action=create_link&cmd=%d' % canal.id
    ).content)['js']
    comprobar('al reproducir, un %s recibe %s' % (tipo, esperado),
              (enlace.get('cmd') or '').split(':')[0], esperado)

Device.objects.filter(uid__startswith='URLS').delete()
User.objects.filter(username='t_urls').delete()
Tariff.objects.filter(name='TEST urls').delete()
Channel.objects.filter(name='TEST canal urls').delete()

print()
if fallos:
    raise SystemExit('FALLAN %d comprobaciones: %s' % (len(fallos), ', '.join(fallos)))
print('Las comprobaciones pasan.')
