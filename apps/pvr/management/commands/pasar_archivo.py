"""
Pasa el archivo (catchup) de unos canales del grabador de Ministra al nuestro.

Los dos graban en la misma carpeta de storage1 (archive/<id de Ministra>/), asi
que no se mueve ni un fichero: Ministra deja de mandar el canal y lo manda
iptv2 a su copia del grabador (storage1n). Lo que hay que cuidar:

  - Que no escriban los dos a la vez el mismo fichero. Esta orden no pasa un
    canal mientras quede un proceso grabando en su carpeta: antes hay que
    quitarlo en Ministra (deploy/ministra/quitar_archivo.php).
  - Que no se borre la semana guardada. El grabador borra lo que pasa de
    "parts_number" horas, y aqui muchos canales tenian 24 donde Ministra manda
    168: se pone lo que mandaba Ministra (--horas).
  - Que no se pise la hora en curso. ffmpeg arranca con -y y empieza de cero el
    fichero de la hora: solo se hace en los primeros minutos de la hora.
  - Que el catchup siga cuadrando. Las medidas de las piezas (piezas.py) van
    por carpeta y la de un grabador nuestro lleva delante su numero: se copian.

  manage.py pasar_archivo --canales 60,61 --simular
  manage.py pasar_archivo --canales 60,61
  manage.py pasar_archivo --canales 60,61 --deshacer   (antes de devolverlo a Ministra)
"""
import subprocess
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.channels.models import Channel
from apps.core.ssh import ssh_bin
from apps.pvr import storage_client
from apps.pvr.models import StorageServer
from apps.stalker_api import piezas
from apps.stalker_api.storage_views import id_en_archivo

MINUTO_LIMITE = 4


def grabando_en(storage, carpetas):
    """Carpetas de `carpetas` en las que hay ahora un proceso grabando; None si
    no se pudo mirar."""
    orden = 'ps -eo args | grep -oE "records/archive/[0-9]+/" | sort -u'
    try:
        p = subprocess.run(
            [ssh_bin(), '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
             '-o', 'ConnectTimeout=8', '-p', str(storage.ssh_port),
             f'{storage.ssh_user}@{storage.ssh_host}', orden],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    vivas = {int(l.strip('/').rsplit('/', 1)[1]) for l in p.stdout.split() if l.strip()}
    return vivas & set(carpetas)


class Command(BaseCommand):
    help = 'Pasa el archivo de unos canales del grabador de Ministra a storage1n'

    def add_arguments(self, parser):
        parser.add_argument('--canales', required=True, help='numeros de canal, con comas')
        parser.add_argument('--grabador', default='storage1n')
        parser.add_argument('--horas', type=int, default=168)
        parser.add_argument('--simular', action='store_true')
        parser.add_argument('--deshacer', action='store_true')
        parser.add_argument('--a-cualquier-hora', action='store_true',
                            help='aunque se pise lo que va de hora')

    def handle(self, *args, **o):
        grabador = StorageServer.objects.filter(
            name=o['grabador'], is_active=True, controlado_por_ministra=False).first()
        if not grabador or not grabador.ssh_host:
            raise CommandError('No hay grabador nuestro %s con acceso para mirarlo' % o['grabador'])
        numeros = [int(n) for n in o['canales'].split(',') if n.strip()]
        canales = list(Channel.objects.filter(number__in=numeros, is_active=True).order_by('number'))
        faltan = set(numeros) - {c.number for c in canales}
        if faltan:
            raise CommandError('No existen los canales %s' % sorted(faltan))

        if o['deshacer']:
            return self.deshacer(canales, grabador, o['simular'])

        for c in canales:
            if c.archivo_en_id:
                raise CommandError('%s ya lo archiva %s' % (c.name, c.archivo_en.name))
            if not (c.has_catchup and c.origen_para_grabar) or c.archive_hls_since:
                raise CommandError('%s: sin archivo o sin direccion para grabar' % c.name)
        carpetas = {id_en_archivo(c): c for c in canales}
        if len(carpetas) != len(canales):
            raise CommandError('Dos canales comparten carpeta')

        ahora = timezone.localtime()
        if ahora.minute > MINUTO_LIMITE and not o['a_cualquier_hora'] and not o['simular']:
            raise CommandError('Son y %02d: se pisaria lo grabado en esta hora. '
                               'Se hace entre y 00 e y %02d.' % (ahora.minute, MINUTO_LIMITE))
        vivas = grabando_en(grabador, carpetas)
        if vivas is None:
            raise CommandError('No se puede mirar el grabador')
        for carpeta, c in carpetas.items():
            self.stdout.write('%3d %-24s carpeta %-4s %s %s h -> %s h%s' % (
                c.number, c.name, carpeta, c.origen_para_grabar, c.timeshift_hours, o['horas'],
                '   TODAVIA GRABA MINISTRA' if carpeta in vivas else ''))
        if o['simular']:
            self.stdout.write('(simulacro: no se ha cambiado nada)')
            return
        if vivas:
            raise CommandError('Aun hay quien graba en esas carpetas: quitar antes en Ministra')

        horas = [ahora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=h)
                 for h in range(0, o['horas'] + 2)]
        for carpeta, c in carpetas.items():
            copiadas = 0
            for hora in horas:
                medida = cache.get(piezas._clave(carpeta, hora))
                if medida is not None:
                    cache.set(piezas._clave('%s:%s' % (grabador.id, carpeta), hora),
                              medida, piezas.GUARDAR)
                    copiadas += 1
            c.timeshift_hours = o['horas']
            c.archivo_en = grabador
            c.save(update_fields=['timeshift_hours', 'archivo_en'])
            try:
                r = storage_client.start_archive(grabador, carpeta, c.origen_para_grabar, o['horas'])
            except storage_client.StorageError as exc:
                r = 'no arranco a mano (%s); lo arrancara solo en menos de 5 min' % exc
            self.stdout.write('%3d %-24s pasado; %d medidas copiadas; arranque: %s' % (
                c.number, c.name, copiadas, r))
        cache.delete('archivo:ventanas')
        cache.delete('archivo:ventanas:%s' % grabador.id)

    def deshacer(self, canales, grabador, simular):
        for c in canales:
            if c.archivo_en_id != grabador.id:
                self.stdout.write('%3d %-24s no lo archiva %s: se deja' % (c.number, c.name, grabador.name))
                continue
            carpeta = id_en_archivo(c)
            self.stdout.write('%3d %-24s carpeta %s: se para y se suelta' % (c.number, c.name, carpeta))
            if simular:
                continue
            c.archivo_en = None
            c.save(update_fields=['archivo_en'])
            try:
                storage_client.stop_archive(grabador, carpeta)
            except storage_client.StorageError as exc:
                self.stdout.write('   no se pudo parar: %s' % exc)
        cache.delete('archivo:ventanas')
