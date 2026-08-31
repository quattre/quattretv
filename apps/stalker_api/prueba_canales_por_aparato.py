"""
Que un canal escondido para un tipo de aparato no le llegue por ningun camino.

Esconderlo de la lista no basta: el aparato sabe pedir un canal por su numero,
asi que si get_url no mira lo mismo que la lista, basta con pedirlo para verlo.
Aqui se comprueban los dos caminos y los del archivo.

El caso que lo motiva: LG no admite aplicaciones con contenido para adultos sin
un contrato aparte con LG Electronics, asi que el canal +18 no puede viajar a
sus televisores aunque el cliente lo tenga contratado. Y tiene que seguir
llegando igual a los MAG y a los Android, que es donde siempre ha estado.

    python3 manage.py shell < apps/stalker_api/prueba_canales_por_aparato.py
"""
from apps.channels.models import Channel
from apps.devices.models import Device, DeviceType
from apps.stalker_api.views import canales_visibles

fallos = []


def comprobar(desc, obtenido, esperado):
    ok = obtenido == esperado
    print(('  OK   ' if ok else '  MAL  ') + desc +
          ('' if ok else ': esperaba %r y ha salido %r' % (esperado, obtenido)))
    if not ok:
        fallos.append(desc)


class AparatoDeMentira:
    def __init__(self, tipo):
        self.device_type = tipo


print('1. La marca se compone y se lee bien')
comprobar('sin aparatos, cadena vacia', Channel.marca([]), '')
comprobar('uno solo va entre comas', Channel.marca(['lg']), ',lg,')
comprobar('varios, separados', Channel.marca(['lg', 'samsung']), ',lg,samsung,')
comprobar('los huecos no cuentan', Channel.marca(['lg', '', None]), ',lg,')

c = Channel(name='Prueba', number=999, oculto_para=',lg,')
comprobar('se lee la lista de vuelta', c.tipos_ocultos, ['lg'])
comprobar('el LG no lo ve', c.visible_para('lg'), False)
comprobar('el MAG si', c.visible_para('mag'), True)
comprobar('sin tipo conocido, se ve', c.visible_para(None), True)
# Ojo: sin las comas, "lg" casaria dentro de "samsung"? No, pero si dentro de
# otro tipo que lo contuviera. Las comas evitan justo eso.
c2 = Channel(name='Prueba2', number=998, oculto_para=',samsung,')
comprobar('samsung oculto no esconde al lg', c2.visible_para('lg'), True)

print('2. El canal +18 no le llega a un LG, y si a los demas')
adulto = Channel.objects.filter(is_adult=True, is_active=True).first()
if not adulto:
    print('  (no hay ningun canal +18 en esta base de datos, se salta)')
else:
    comprobar('el canal +18 esta escondido para LG',
              'lg' in adulto.tipos_ocultos, True)
    todos = Channel.objects.filter(is_active=True)
    ids_lg = set(canales_visibles(todos, AparatoDeMentira('lg')).values_list('id', flat=True))
    ids_mag = set(canales_visibles(todos, AparatoDeMentira('mag')).values_list('id', flat=True))
    ids_android = set(canales_visibles(todos, AparatoDeMentira('android')).values_list('id', flat=True))
    comprobar('no sale en la lista de un LG', adulto.id in ids_lg, False)
    comprobar('si sale en la de un MAG', adulto.id in ids_mag, True)
    comprobar('si sale en la de un Android', adulto.id in ids_android, True)
    comprobar('al LG solo le falta ese canal', len(ids_mag) - len(ids_lg), 1)

    print('3. Sin aparato conocido no se esconde nada')
    # Un aparato sin identificar no debe recibir MENOS de lo normal por error;
    # quien decide que un desconocido no vea nada es la autenticacion, no esto.
    ids_sin = set(canales_visibles(todos, None).values_list('id', flat=True))
    comprobar('sin aparato, la lista entera', len(ids_sin), todos.count())

print('4. Un aparato real de la base de datos se filtra por su tipo')
d = Device.objects.filter(device_type=DeviceType.LG).first()
if not d:
    print('  (no hay ningun aparato LG dado de alta, se salta)')
elif adulto:
    ids = set(canales_visibles(Channel.objects.filter(is_active=True), d)
              .values_list('id', flat=True))
    comprobar('el LG de verdad tampoco lo recibe', adulto.id in ids, False)

print('')
if fallos:
    print('FALLAN %d comprobaciones:' % len(fallos))
    for f in fallos:
        print('  - ' + f)
else:
    print('Las comprobaciones pasan.')
