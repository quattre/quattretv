"""
Pasa las URLs de los canales de http://cdnX:1500 a https://cdnX.

Hace falta porque la app de television y el portal van por https, y un navegador
— y webOS lleva Chromium dentro — se niega a cargar video por http desde una
pagina servida por https. Sin esto, en la LG no se ve nada.

Los CDN sirven ahora las dos cosas: el puerto 1500 en claro, que es por donde
entran los decos que cuelgan del middleware viejo, y el 443 con certificado.
Esto solo cambia la direccion que se le entrega al aparato; en los CDN no se
toca nada.

Antes de cambiar nada comprueba que la direccion nueva responde de verdad, asi
que si el certificado o el cortafuegos no estuvieran en su sitio no deja los
canales apuntando a un sitio que no contesta. Se vuelve atras con --revertir.
"""
import re

from django.core.management.base import BaseCommand

from apps.channels.models import Channel

# http://cdn10.quattre.com:1500/hls/la1/index.m3u8
#   -> https://cdn10.quattre.com/hls/la1/index.m3u8
A_HTTPS = (r'^http://([a-z0-9.-]+):1500/', r'https://\1/')
A_HTTP = (r'^https://([a-z0-9.-]+)/hls/', r'http://\1:1500/hls/')


class Command(BaseCommand):
    help = 'Pasa las URLs de los canales a https (o vuelve atras con --revertir)'

    def add_arguments(self, parser):
        parser.add_argument('--revertir', action='store_true',
                            help='Volver a http y el puerto 1500')
        parser.add_argument('--simular', action='store_true',
                            help='Enseñar lo que haria sin tocar nada')
        parser.add_argument('--sin-comprobar', action='store_true',
                            help='No pedir cada URL nueva antes de guardarla')

    def handle(self, *args, **options):
        patron, reemplazo = A_HTTP if options['revertir'] else A_HTTPS
        comprobar = not options['sin_comprobar'] and not options['revertir']

        pendientes = []
        for ch in Channel.objects.all().order_by('number'):
            actual = ch.stream_url or ''
            nueva = re.sub(patron, reemplazo, actual)
            if nueva != actual:
                pendientes.append((ch, actual, nueva))

        if not pendientes:
            self.stdout.write(self.style.SUCCESS(
                'Nada que cambiar: todas las URLs ya estan como se pide.'
            ))
            return

        self.stdout.write('%d canales por cambiar (de %d).' % (
            len(pendientes), Channel.objects.count()
        ))

        if options['simular']:
            for ch, actual, nueva in pendientes:
                self.stdout.write('  %-22s %s\n  %-22s -> %s' % (
                    ch.name, actual, '', nueva))
            self.stdout.write(self.style.WARNING('Simulacion: no se ha tocado nada.'))
            return

        cambiados = 0
        fallan = []
        for ch, actual, nueva in pendientes:
            if comprobar and not self._responde(nueva):
                fallan.append((ch.name, nueva))
                continue
            ch.stream_url = nueva
            ch.save(update_fields=['stream_url'])
            cambiados += 1

        self.stdout.write(self.style.SUCCESS('Cambiados %d canales.' % cambiados))

        if fallan:
            self.stdout.write(self.style.ERROR(
                '%d se han quedado como estaban porque su URL nueva no responde:'
                % len(fallan)
            ))
            for nombre, url in fallan:
                self.stdout.write('  %-22s %s' % (nombre, url))
            self.stdout.write(
                'Revisa el certificado del CDN y que el puerto 443 este abierto. '
                'Con --sin-comprobar se guardarian igual.'
            )

    def _responde(self, url):
        """True si la playlist se puede pedir de verdad por esa direccion."""
        import urllib.request
        try:
            peticion = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(peticion, timeout=10) as r:
                return r.status == 200
        except Exception:
            return False
