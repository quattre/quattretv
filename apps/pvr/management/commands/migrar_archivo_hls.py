"""
Migra el archivo de un canal de MPEG-TS a HLS sin cortar el servicio.

El orden importa: primero se arranca el grabador nuevo (fuera de aqui, en el
storage), y solo despues se ejecuta esto. A partir de ese momento el catchup
nuevo se sirve en HLS y el anterior se sigue sirviendo del archivo viejo hasta
que caduca solo. Nada se borra y se puede volver atras con --revertir.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.channels.models import Channel
from apps.pvr import storage_client
from datetime import datetime

from apps.stalker_api.storage_views import (
    almacen_archivo, archive_storage, fetch_segment_index, id_en_archivo)


class Command(BaseCommand):
    help = 'Marca canales como archivados en HLS y para su grabador antiguo'

    def add_arguments(self, parser):
        parser.add_argument(
            'numeros', nargs='*', type=int,
            help='Numeros de canal a migrar (vacio con --todos para todos)'
        )
        parser.add_argument('--todos', action='store_true',
                            help='Migrar todos los canales con archivo')
        parser.add_argument('--revertir', action='store_true',
                            help='Volver al archivo en MPEG-TS')
        parser.add_argument('--margen', type=int, default=60,
                            help='Segundos de solape para no dejar hueco (por defecto 60)')
        parser.add_argument('--desde', default='',
                            help="Servir en HLS desde esta hora (hora de Madrid, "
                                 "'2026-11-23 18:00'): lo que el grabador nuevo ya tiene "
                                 "grabado. Sin esto, desde ahora")
        parser.add_argument('--simular', action='store_true',
                            help='Enseñar lo que haria sin tocar nada')

    def handle(self, *args, **options):
        channels = Channel.objects.filter(is_active=True, has_catchup=True)
        if not options['todos']:
            if not options['numeros']:
                raise CommandError('Indica numeros de canal o usa --todos')
            channels = channels.filter(number__in=options['numeros'])

        if not channels.exists():
            raise CommandError('Ningun canal coincide')

        storage = archive_storage()
        if not storage and not options['simular']:
            raise CommandError('No hay servidor de archivo activo configurado')

        for channel in channels.order_by('number'):
            if options['revertir']:
                self._revertir(channel, options['simular'])
            else:
                self._migrar(channel, storage, options['margen'], options['simular'],
                             self._hora(options['desde']))

    def _hora(self, texto):
        if not texto:
            return None
        try:
            hora = datetime.strptime(texto, '%Y-%m-%d %H:%M')
        except ValueError:
            raise CommandError("--desde va como '2026-11-23 18:00' (hora de Madrid)")
        return timezone.make_aware(hora)

    def _migrar(self, channel, storage, margen, simular, desde=None):
        if channel.archive_hls_since:
            self.stdout.write(f'  {channel.number} {channel.name}: ya estaba migrado')
            return

        if desde is None:
            # El solape hacia atras evita que quede un hueco de unos segundos entre
            # lo ultimo que escribio el grabador viejo y lo primero del nuevo.
            desde = timezone.now() - timezone.timedelta(seconds=margen)
        # Que el grabador nuevo de verdad tenga trozos desde ahi: si no, el
        # catchup de ese rato contestaria una lista vacia.
        if storage:
            trozos = fetch_segment_index(storage, channel, desde, desde + timezone.timedelta(minutes=1))
            if not trozos:
                raise CommandError(
                    f'{channel.number} {channel.name}: el archivo HLS no tiene trozos de {desde}. '
                    '¿Esta en marcha quattretv-archive@%s en storage1?' % channel.id)

        if simular:
            self.stdout.write(
                f'  {channel.number} {channel.name}: marcaria HLS desde {desde} '
                'y pararia el grabador antiguo'
            )
            return

        channel.archive_hls_since = desde
        channel.save(update_fields=['archive_hls_since'])

        # Ya no aparecera en la lista de tareas, pero el proceso que hay en
        # marcha hay que pararlo explicitamente.
        try:
            storage_client.stop_archive(almacen_archivo(channel) or storage, id_en_archivo(channel))
            parado = 'grabador antiguo parado'
        except storage_client.StorageError as exc:
            parado = f'AVISO: no se pudo parar el grabador antiguo ({exc})'

        self.stdout.write(self.style.SUCCESS(
            f'  {channel.number} {channel.name}: HLS desde {desde} - {parado}'
        ))

    def _revertir(self, channel, simular):
        if not channel.archive_hls_since:
            self.stdout.write(f'  {channel.number} {channel.name}: no estaba migrado')
            return
        if simular:
            self.stdout.write(f'  {channel.number} {channel.name}: volveria a MPEG-TS')
            return

        channel.archive_hls_since = None
        channel.save(update_fields=['archive_hls_since'])
        self.stdout.write(self.style.WARNING(
            f'  {channel.number} {channel.name}: vuelto a MPEG-TS. El grabador '
            'antiguo lo recogera solo en el proximo ciclo (5 min).'
        ))
