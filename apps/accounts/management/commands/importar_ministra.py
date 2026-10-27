"""
Copia cuentas de Ministra a la plataforma nueva, con su deco, sus favoritos y
sus grabaciones.

Mientras convivan las dos, **Ministra sigue mandando** y esto es una copia que
se puede repetir cuantas veces haga falta (la idea es cada noche): actualiza lo
que ya trajo en vez de duplicarlo, y no toca nunca una cuenta creada aqui.

Lo que hay que saber de Ministra para entender el resto:
- Una cuenta es un deco: cada fila de `users` tiene su login y una sola MAC.
- La contraseña es md5(md5(contraseña) + id); se copia tal cual y Django la
  pasa a su formato al primer acceso (apps/accounts/hashers.py).
- `status` 0 es activa y 1 apagada.
- Los canales van por su id interno, asi que antes hay que haber lanzado
  vincular_canales_ministra.

Las grabaciones se traen como completadas (o programadas o en curso, segun
esten alli) y apuntando al grabador que las tiene, que es de Ministra: nunca se
le manda una orden desde aqui, solo se reproduce lo que ya existe.
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Tariff, User
from apps.channels.models import Channel, Favorite
from apps.core import ministra
from apps.stalker_api.authentication import MACAuthentication
from apps.devices.models import Device
from apps.pvr.models import Recording, RecordingStatus, StorageServer

# Plan de Ministra (tariff_plan.id) -> tarifa de aqui. Se puede cambiar con
# --tarifas sin tocar el codigo.
TARIFAS_POR_DEFECTO = '0=Completa,2=Completa,6=Completa,4=Completa sin adultos,5=Tablet,7=Tablet'
GRABADOR_POR_DEFECTO = 'record1b'


def fecha(valor):
    """Las fechas de Ministra son hora de Madrid sin zona; 0000-00-00 = nada."""
    if not valor or valor.startswith('0000'):
        return None
    return timezone.make_aware(datetime.strptime(valor, '%Y-%m-%d %H:%M:%S'))


class Command(BaseCommand):
    help = 'Copia cuentas, decos, favoritos y grabaciones de Ministra'

    def add_arguments(self, parser):
        quien = parser.add_mutually_exclusive_group(required=True)
        quien.add_argument('--login', action='append', metavar='LOGIN',
                           help='Solo esta cuenta (se puede repetir)')
        quien.add_argument('--mac', action='append', metavar='MAC',
                           help='Solo la cuenta de este deco (se puede repetir)')
        quien.add_argument('--todos', action='store_true',
                           help='Todas las cuentas de Ministra')
        parser.add_argument('--simular', action='store_true',
                            help='Hacerlo todo y deshacerlo al final, para ver que pasaria')
        parser.add_argument('--tarifas', default=TARIFAS_POR_DEFECTO,
                            help=f'Plan de Ministra = tarifa de aqui (por defecto "{TARIFAS_POR_DEFECTO}")')
        parser.add_argument('--grabador', default=GRABADOR_POR_DEFECTO,
                            help='StorageServer que tiene las grabaciones de Ministra '
                                 f'(por defecto {GRABADOR_POR_DEFECTO})')
        parser.add_argument('--sin-grabaciones', action='store_true',
                            help='Copiar solo cuentas, decos y favoritos')

    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.simular = options['simular']
        self.avisos = []
        self.cuenta = {k: 0 for k in (
            'cuentas_nuevas', 'cuentas_actualizadas', 'cuentas_apagadas',
            'decos_nuevos', 'favoritos', 'grabaciones_nuevas',
            'grabaciones_actualizadas', 'grabaciones_borradas', 'saltadas')}

        tarifas = self._tarifas(options['tarifas'])
        self.canales = {c.ministra_id: c for c in Channel.objects.exclude(ministra_id=None)}
        if not self.canales:
            raise CommandError('Ningun canal esta unido con Ministra: lanza antes '
                               'vincular_canales_ministra.')

        grabador = None
        if not options['sin_grabaciones']:
            grabador = StorageServer.objects.filter(name=options['grabador']).first()
            if not grabador:
                raise CommandError(f'No hay ningun grabador llamado {options["grabador"]}')
            if not grabador.controlado_por_ministra:
                raise CommandError(
                    f'{grabador.name} no esta marcado como "controlado por Ministra". '
                    'Las grabaciones viejas no se pueden asignar a un grabador al que '
                    'esta plataforma da ordenes.')

        filas = self._leer_cuentas(options)
        if not filas:
            raise CommandError('Ministra no devolvio ninguna cuenta con ese filtro')
        self.stdout.write(f'{len(filas)} cuentas leidas de Ministra')

        favoritos = {int(f['uid']): f['fav_ch'] for f in ministra.consultar(
            f'SELECT uid, fav_ch FROM fav_itv WHERE uid IN ({ministra.lista_de_ids(r["id"] for r in filas)})')}

        with transaction.atomic():
            usuarios = {}
            for fila in filas:
                usuario = self._cuenta(fila, tarifas)
                if usuario:
                    usuarios[int(fila['id'])] = usuario
                    self._deco(fila, usuario)
                    self._favoritos(usuario, favoritos.get(int(fila['id'])))

            if options['todos']:
                self._apagar_desaparecidas({int(f['id']) for f in filas})

            if grabador and usuarios:
                self._grabaciones(usuarios, grabador)

            if self.simular:
                transaction.set_rollback(True)

        for aviso in self.avisos[:50]:
            self.stdout.write(self.style.WARNING(aviso))
        if len(self.avisos) > 50:
            self.stdout.write(self.style.WARNING(f'... y {len(self.avisos) - 50} avisos mas'))

        titulo = 'SIMULACRO, no se ha guardado nada' if self.simular else 'Hecho'
        self.stdout.write(self.style.SUCCESS(
            f'{titulo}: ' + ' · '.join(f'{k.replace("_", " ")}: {v}' for k, v in self.cuenta.items())))

    # ------------------------------------------------------------------

    def _tarifas(self, texto):
        mapa, faltan = {}, []
        for trozo in texto.split(','):
            if '=' not in trozo:
                continue
            plan, nombre = trozo.split('=', 1)
            tarifa = Tariff.objects.filter(name__iexact=nombre.strip()).first()
            if not tarifa:
                faltan.append(nombre.strip())
            mapa[int(plan)] = tarifa
        if faltan:
            existentes = ', '.join(Tariff.objects.values_list('name', flat=True)) or 'ninguna'
            mensaje = (f'Faltan tarifas por crear en el panel: {", ".join(sorted(set(faltan)))}. '
                       f'Existen: {existentes}. Se pueden traducir a otras con --tarifas.')
            if not self.simular:
                raise CommandError(mensaje)
            self.avisos.append(mensaje + ' (en el simulacro se dejan sin tarifa)')
        return mapa

    def _leer_cuentas(self, options):
        campos = ('id, login, password, mac, status, fname, comment, stb_type, '
                  'serial_number, tariff_plan_id, created')
        if options['todos']:
            donde = '1'
        elif options['login']:
            nombres = ','.join("'" + l.replace("\\", "").replace("'", "") + "'" for l in options['login'])
            donde = f'login IN ({nombres})'
        else:
            macs = [MACAuthentication.normalize_mac(m) for m in options['mac']]
            donde = 'UPPER(mac) IN (' + ','.join(f"'{m}'" for m in macs if m) + ')'
        return ministra.consultar(f'SELECT {campos} FROM users WHERE {donde} ORDER BY id')

    def _cuenta(self, fila, tarifas):
        mid = int(fila['id'])
        login = (fila['login'] or '').strip()
        if not login:
            self.avisos.append(f'Cuenta {mid} de Ministra sin login: no se copia')
            self.cuenta['saltadas'] += 1
            return None

        usuario = User.objects.filter(ministra_id=mid).first()
        if not usuario:
            ajena = User.objects.filter(username=login).first()
            if ajena:
                self.avisos.append(
                    f'"{login}" ya existe aqui y no viene de Ministra: no se toca')
                self.cuenta['saltadas'] += 1
                return None
            usuario = User(ministra_id=mid, username=login)
            self.cuenta['cuentas_nuevas'] += 1
        else:
            self.cuenta['cuentas_actualizadas'] += 1

        usuario.username = login
        usuario.first_name = (fila['fname'] or '')[:150]
        usuario.is_active = fila['status'] == '0'
        usuario.tariff = tarifas.get(int(fila['tariff_plan_id'] or 0))
        if fila['comment'] and not usuario.notes:
            usuario.notes = fila['comment']

        hash_ministra = (fila['password'] or '').lower()
        if len(hash_ministra) == 32:
            nuevo = f'ministra${mid}${hash_ministra}'
            # Si el cliente ya entro aqui, su contraseña esta en el formato de
            # Django y es la misma: no se pisa. Si sigue en el de Ministra, se
            # refresca por si la han cambiado alli.
            if not usuario.password or usuario.password.startswith('ministra$'):
                usuario.password = nuevo
        elif not usuario.password:
            usuario.set_unusable_password()
            self.avisos.append(f'"{login}" no tiene contraseña valida en Ministra')

        creado = fecha(fila['created'])
        if creado and not usuario.pk:
            usuario.date_joined = creado
        usuario.save()
        return usuario

    def _deco(self, fila, usuario):
        mac = MACAuthentication.normalize_mac(fila['mac'] or '')
        if not mac:
            return
        deco = Device.objects.filter(mac_address=mac).first()
        if deco and deco.user_id != usuario.id:
            self.avisos.append(
                f'La MAC {mac} de "{usuario.username}" ya es de "{deco.user.username}" aqui: no se mueve')
            return
        if not deco:
            deco = Device(user=usuario, mac_address=mac, device_type='mag', is_active=True)
            self.cuenta['decos_nuevos'] += 1
        deco.model = (fila['stb_type'] or '')[:100]
        deco.serial_number = (fila['serial_number'] or '')[:100]
        deco.name = f'{fila["stb_type"] or "MAG"} - {usuario.username}'[:100]
        deco.save()

    def _favoritos(self, usuario, fav_ch):
        ids = ministra.favoritos(fav_ch)
        canales = []
        for mid in ids:
            canal = self.canales.get(mid)
            if canal and canal not in canales:
                canales.append(canal)
        actuales = list(Favorite.objects.filter(user=usuario).order_by('order')
                        .values_list('channel_id', flat=True))
        if actuales == [c.id for c in canales]:
            return
        Favorite.objects.filter(user=usuario).delete()
        Favorite.objects.bulk_create(
            Favorite(user=usuario, channel=canal, order=orden)
            for orden, canal in enumerate(canales))
        self.cuenta['favoritos'] += 1

    def _apagar_desaparecidas(self, vistos):
        """Una cuenta borrada en Ministra se apaga aqui; no se borra."""
        for usuario in User.objects.exclude(ministra_id=None).filter(is_active=True):
            if usuario.ministra_id not in vistos:
                usuario.is_active = False
                usuario.save(update_fields=['is_active'])
                self.cuenta['cuentas_apagadas'] += 1

    def _grabaciones(self, usuarios, grabador):
        filas = ministra.consultar(
            'SELECT u.id, u.uid, u.ch_id, u.program, u.t_start, u.t_stop, u.length, '
            'u.started, u.ended, r.file_name, r.storage_name '
            'FROM users_rec u LEFT JOIN rec_files r ON r.id = u.file_id '
            f'WHERE u.uid IN ({ministra.lista_de_ids(usuarios)})')

        vistas = set()
        for fila in filas:
            mid = int(fila['id'])
            usuario = usuarios.get(int(fila['uid']))
            canal = self.canales.get(int(fila['ch_id']))
            if not canal:
                self.avisos.append(
                    f'Grabacion {mid} de "{usuario.username}" es de un canal sin pareja '
                    f'(Ministra {fila["ch_id"]}): no se copia')
                self.cuenta['saltadas'] += 1
                continue
            inicio, fin = fecha(fila['t_start']), fecha(fila['t_stop'])
            if not inicio or not fin:
                continue

            if fila['ended'] == '1':
                estado = RecordingStatus.COMPLETED
            elif fila['started'] == '1':
                estado = RecordingStatus.RECORDING
            else:
                estado = RecordingStatus.SCHEDULED

            datos = {
                'user': usuario,
                'channel': canal,
                'title': (fila['program'] or canal.name)[:300],
                'start_time': inicio,
                'end_time': fin,
                'status': estado,
                'storage': grabador,
                'filename': fila['file_name'] or '',
                'container': 'ts',
                'duration': int(fila['length'] or 0) or int((fin - inicio).total_seconds()),
            }
            grabacion = Recording.objects.filter(ministra_id=mid).first()
            if grabacion:
                cambios = [k for k, v in datos.items() if getattr(grabacion, k) != v]
                if cambios:
                    for k in cambios:
                        setattr(grabacion, k, datos[k])
                    grabacion.save(update_fields=cambios)
                    self.cuenta['grabaciones_actualizadas'] += 1
            else:
                Recording.objects.create(ministra_id=mid, **datos)
                self.cuenta['grabaciones_nuevas'] += 1
            vistas.add(mid)

        # Lo que el cliente borro en Ministra desaparece tambien aqui. Solo la
        # ficha: el fichero es de Ministra y lo borra ella.
        sobrantes = Recording.objects.filter(
            user__in=usuarios.values()).exclude(ministra_id=None).exclude(ministra_id__in=vistas)
        self.cuenta['grabaciones_borradas'] += sobrantes.count()
        sobrantes.delete()
