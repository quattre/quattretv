"""
Comprueba que los servidores de grabación están bien enganchados.

Sirve para no descubrir a base de quejas que un grabador dejó de pedir tareas o
que el listado del archivo no se ve. Solo lee: no manda grabar nada.
"""
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.channels.models import Channel
from apps.pvr.models import StorageServer
from apps.stalker_api.storage_views import fetch_segment_index

TIMEOUT = 10


class Command(BaseCommand):
    help = 'Diagnostico de los servidores de grabacion (record1 / storage1)'

    def add_arguments(self, parser):
        parser.add_argument('--nombre', help='Comprobar solo este storage')

    def handle(self, *args, **options):
        servidores = StorageServer.objects.filter(is_active=True)
        if options['nombre']:
            servidores = servidores.filter(name=options['nombre'])

        if not servidores.exists():
            self.stdout.write(self.style.ERROR(
                'No hay ningun servidor de grabacion activo dado de alta. '
                'Se crean en el admin de Django, en Storage Servers.'
            ))
            return

        for servidor in servidores:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'\n{servidor.name} ({servidor.get_role_display()})'
            ))
            self._ultimo_contacto(servidor)
            self._alcanzable(servidor)
            if servidor.records_archive:
                self._archivo(servidor)

    def _ultimo_contacto(self, servidor):
        if not servidor.last_sync:
            self.stdout.write(self.style.WARNING(
                '  - Nunca ha pedido sus tareas de archivo. Revisa API_URL en '
                'su config.php y que tvarchivetasks.service este arrancado.'
            ))
            return

        minutos = (timezone.now() - servidor.last_sync).total_seconds() / 60
        texto = f'  - Ultimo contacto hace {minutos:.0f} min'
        if minutos > 15:
            self.stdout.write(self.style.ERROR(texto + ' (deberia ser cada 5)'))
        else:
            self.stdout.write(self.style.SUCCESS(texto))

    def _alcanzable(self, servidor):
        url = servidor.build_url('', public=True)
        try:
            respuesta = requests.get(url, timeout=TIMEOUT)
            self.stdout.write(self.style.SUCCESS(
                f'  - Responde en {url} ({respuesta.status_code})'
            ))
        except requests.RequestException as exc:
            self.stdout.write(self.style.ERROR(f'  - No responde en {url}: {exc}'))

    def _archivo(self, servidor):
        canales = Channel.objects.filter(
            is_active=True, has_catchup=True, archive_hls_since__isnull=False
        ).exclude(multicast_url='')

        if not canales.exists():
            self.stdout.write(
                '  - Ningun canal migrado a HLS todavia '
                '(manage.py migrar_archivo_hls)'
            )
            return

        for canal in canales[:10]:
            segmentos = fetch_segment_index(servidor, canal)
            if not segmentos:
                self.stdout.write(self.style.ERROR(
                    f'  - Canal {canal.number} {canal.name}: sin segmentos. '
                    'Revisa el autoindex json de nginx y que el ffmpeg del '
                    'canal este grabando.'
                ))
                continue

            primero, ultimo = segmentos[0][0], segmentos[-1][0]
            retraso = (timezone.now() - ultimo).total_seconds()
            texto = (f'  - Canal {canal.number} {canal.name}: {len(segmentos)} '
                     f'segmentos, de {primero:%d/%m %H:%M} a {ultimo:%d/%m %H:%M}')
            if retraso > 120:
                self.stdout.write(self.style.ERROR(
                    texto + f' — el ultimo tiene {retraso / 60:.0f} min, esta parado'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(texto))
