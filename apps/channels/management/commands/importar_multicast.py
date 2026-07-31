"""
Trae el origen multicast de cada canal leyendo la configuración del CDN.

En el CDN hay un fichero por canal en /home/quattre/canales/<nombre> con
`SRC=udp://ip:puerto`, que es justo lo que necesitan los grabadores. Copiarlo a
mano para 177 canales no es plan, y equivocarse en uno significa que ese canal
no se graba.

Solo lee: no toca nada en el CDN.
"""
import re
import subprocess

from django.core.management.base import BaseCommand, CommandError

from apps.channels import cdn as cdn_tools
from apps.channels.models import CdnServer, Channel

RUTA_CANALES = '/home/quattre/canales'
TIMEOUT = 30


class Command(BaseCommand):
    help = 'Rellena multicast_url de los canales leyendo los EnvironmentFile del CDN'

    def add_arguments(self, parser):
        parser.add_argument('cdn', help='Nombre del CDN dado de alta en el panel')
        parser.add_argument('--ruta', default=RUTA_CANALES,
                            help=f'Directorio de configuración en el CDN (por defecto {RUTA_CANALES})')
        parser.add_argument('--simular', action='store_true',
                            help='Enseñar lo que haría sin guardar nada')
        parser.add_argument('--sobrescribir', action='store_true',
                            help='Cambiar también los que ya tienen origen puesto')

    def handle(self, *args, **options):
        try:
            servidor = CdnServer.objects.get(name=options['cdn'])
        except CdnServer.DoesNotExist:
            raise CommandError(
                f"No hay ningún CDN llamado '{options['cdn']}'. "
                f"Dados de alta: {', '.join(CdnServer.objects.values_list('name', flat=True)) or 'ninguno'}"
            )

        if not servidor.ssh_host:
            raise CommandError(f'El CDN {servidor.name} no tiene acceso SSH configurado')

        fuentes = self._leer_del_cdn(servidor, options['ruta'])
        if not fuentes:
            raise CommandError('No se pudo leer ningún canal del CDN')

        self.stdout.write(f'{len(fuentes)} canales leídos de {servidor.name}')

        puestos = saltados = sin_pareja = 0
        for canal in Channel.objects.filter(is_active=True).order_by('number'):
            nombre = cdn_tools.nombre_en_cdn(canal)
            if not nombre or nombre not in fuentes:
                continue

            origen = fuentes[nombre]
            if canal.multicast_url and not options['sobrescribir']:
                if canal.multicast_url != origen:
                    self.stdout.write(self.style.WARNING(
                        f'  {canal.number} {canal.name}: ya tenía {canal.multicast_url}, '
                        f'en el CDN pone {origen} (usa --sobrescribir)'
                    ))
                saltados += 1
                continue

            if options['simular']:
                self.stdout.write(f'  {canal.number} {canal.name}: pondría {origen}')
            else:
                canal.multicast_url = origen
                if not canal.cdn_id:
                    canal.cdn = servidor
                if not canal.cdn_name:
                    canal.cdn_name = nombre
                canal.save(update_fields=['multicast_url', 'cdn', 'cdn_name'])
            puestos += 1

        # Canales del CDN que no encajan con ninguno nuestro: suelen ser
        # renombrados o dados de baja, y conviene verlos.
        nuestros = {
            cdn_tools.nombre_en_cdn(c)
            for c in Channel.objects.filter(is_active=True)
        }
        sin_pareja = sorted(set(fuentes) - nuestros)

        self.stdout.write(self.style.SUCCESS(
            f'\n{puestos} canales con origen multicast'
            + (' (simulado)' if options['simular'] else '')
        ))
        if saltados:
            self.stdout.write(f'{saltados} ya lo tenían (usa --sobrescribir para cambiarlos)')
        if sin_pareja:
            self.stdout.write(self.style.WARNING(
                f'{len(sin_pareja)} canales en el CDN sin canal equivalente aquí: '
                + ', '.join(sin_pareja[:15]) + ('...' if len(sin_pareja) > 15 else '')
            ))

    def _leer_del_cdn(self, servidor, ruta):
        """Un solo SSH que vuelca todos los ficheros con su nombre delante."""
        orden = [
            'ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'ConnectTimeout=8', '-p', str(servidor.ssh_port),
            f'{servidor.ssh_user}@{servidor.ssh_host}',
            f'for f in {ruta}/*; do echo "@@$(basename $f)"; grep -h "^SRC=" "$f" 2>/dev/null; done',
        ]

        try:
            proceso = subprocess.run(orden, capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            raise CommandError('El CDN no respondió a tiempo')
        except OSError as exc:
            raise CommandError(f'No se pudo ejecutar ssh: {exc}')

        if proceso.returncode != 0:
            raise CommandError(
                'Fallo al leer del CDN: ' + (proceso.stderr or '').strip()[:200]
            )

        fuentes = {}
        nombre = None
        for linea in proceso.stdout.splitlines():
            if linea.startswith('@@'):
                nombre = linea[2:].strip()
                continue
            match = re.match(r'\s*SRC=(\S+)', linea)
            if match and nombre:
                fuentes[nombre] = match.group(1)
                nombre = None

        return fuentes
