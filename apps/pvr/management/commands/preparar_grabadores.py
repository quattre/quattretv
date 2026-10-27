"""
Da de alta en el panel los grabadores de record1 tal y como quedan al convivir.

Despues de instalar deploy/storage/copia_grabador.sh hay dos grabadores en la
misma maquina:
  - record1b, el de Ministra: aqui solo se leen sus grabaciones antiguas.
  - record1n, la copia que obedece a esta plataforma: graba lo nuevo.
Escribir estas direcciones a mano en el admin es facil de equivocar, y un error
en la del de Ministra le mandaria ordenes que no son nuestras.
"""
import secrets

from django.core.management.base import BaseCommand

from apps.pvr.models import StorageRole, StorageServer

PUERTA = 'http://185.25.27.50:2222/stalker_portal'


class Command(BaseCommand):
    help = 'Configura record1b (Ministra, solo lectura) y record1n (el nuestro)'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true')

    def handle(self, *args, **options):
        fichas = [
            ('record1b', {
                'role': StorageRole.RECORDS,
                'controlado_por_ministra': True,
                'api_url': f'{PUERTA}/storage/',
                'playback_url': f'{PUERTA}/quattretv_grab/ministra/',
                'secure_link_secret': '',
                'ssh_host': '185.25.27.50', 'ssh_port': 2221, 'ssh_user': 'quattre',
                'is_active': True,
            }),
            ('record1n', {
                'role': StorageRole.RECORDS,
                'controlado_por_ministra': False,
                'api_url': f'{PUERTA}/quattretv_storage/',
                'playback_url': f'{PUERTA}/quattretv_grab/nuevas/',
                'secure_link_secret': '',
                'ssh_host': '185.25.27.50', 'ssh_port': 2221, 'ssh_user': 'quattre',
                'is_active': True,
            }),
        ]
        for nombre, datos in fichas:
            actual = StorageServer.objects.filter(name=nombre).first()
            if actual and actual.token:
                datos = dict(datos, token=actual.token)
            else:
                # Lo pide el grabador al borrar ficheros (chk_storage_token.php).
                datos = dict(datos, token=secrets.token_hex(16))
            self.stdout.write(f'{"cambiar" if actual else "crear"} {nombre}:')
            for campo, valor in datos.items():
                antes = getattr(actual, campo, None) if actual else None
                if antes != valor:
                    self.stdout.write(f'    {campo}: {antes!r} -> {valor!r}')
            if not options['simular']:
                StorageServer.objects.update_or_create(name=nombre, defaults=datos)
        if options['simular']:
            self.stdout.write('(simulacro: no se ha guardado nada)')
