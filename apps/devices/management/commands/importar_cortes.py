"""
Saca los cortes de conexion del registro de nginx y los guarda
(apps/devices/cortes.py). Se puede repetir: los que ya estan no se duplican.

  manage.py importar_cortes                  el registro de hoy (cron, cada 15 min)
  manage.py importar_cortes RUTA [RUTA...]   esos ficheros (.gz tambien), p. ej.
                                             los de dias anteriores
"""
import os
import time

from django.core.management.base import BaseCommand

from apps.devices import cortes

REGISTROS = ['/var/log/nginx/iptv1.access.log', '/var/log/nginx/iptv2.access.log']


class Command(BaseCommand):
    help = 'Guarda los cortes de conexion que se ven en el registro de nginx'

    def add_arguments(self, parser):
        parser.add_argument('rutas', nargs='*')

    def handle(self, *args, **opciones):
        rutas = opciones['rutas']
        if not rutas:
            rutas = [r for r in REGISTROS if os.path.exists(r)]
            # Recien girado el registro (a medianoche), lo de ayer esta en .1.
            ayer = [r + '.1' for r in rutas if os.path.exists(r + '.1')
                    and time.time() - os.path.getmtime(r + '.1') < 3 * 3600]
            rutas = ayer + rutas
        for ruta in rutas:
            n = cortes.importar_registro([ruta])
            if n or opciones['rutas']:
                self.stdout.write('%s: %d cortes nuevos' % (ruta, n))
