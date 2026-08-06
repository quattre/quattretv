"""
Rellena el logotipo de cada canal con el que trae la fuente de EPG.

Los canales estaban todos sin logotipo, asi que el portal no pintaba ninguno
aunque el codigo los soporta. Las guias XMLTV traen el icono de cada canal, y
como los canales ya estan emparejados con la guia, se puede aprovechar.
"""
import gzip
import io
import xml.etree.ElementTree as ET

import requests
from django.core.management.base import BaseCommand

from apps.channels.models import Channel
from apps.epg.models import EpgSource

TIMEOUT = 180


class Command(BaseCommand):
    help = 'Trae el logotipo de los canales desde las fuentes de EPG'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true',
                            help='Enseñar lo que haria sin guardar')
        parser.add_argument('--sobrescribir', action='store_true',
                            help='Cambiar tambien los que ya tienen logotipo')

    def handle(self, *args, **options):
        canales = Channel.objects.filter(is_active=True).exclude(epg_id='')
        if not options['sobrescribir']:
            canales = canales.filter(logo_url='')

        pendientes = {c.epg_id: c for c in canales}
        if not pendientes:
            self.stdout.write('Todos los canales tienen ya su logotipo.')
            return

        self.stdout.write(f'{len(pendientes)} canales sin logotipo\n')
        puestos = 0

        for fuente in EpgSource.objects.filter(is_active=True):
            if not pendientes:
                break

            iconos = self._iconos_de(fuente.url)
            if not iconos:
                continue

            encontrados = 0
            for epg_id, canal in list(pendientes.items()):
                url = iconos.get(epg_id)
                if not url:
                    continue
                if not options['simular']:
                    canal.logo_url = url
                    canal.save(update_fields=['logo_url'])
                del pendientes[epg_id]
                puestos += 1
                encontrados += 1

            self.stdout.write(f'  {fuente.name}: {encontrados} logotipos')

        self.stdout.write(self.style.SUCCESS(
            f'\n{puestos} canales con logotipo'
            + (' (simulado)' if options['simular'] else '')))
        if pendientes:
            self.stdout.write(self.style.WARNING(
                f'{len(pendientes)} sin encontrar: '
                + ', '.join(c.name for c in list(pendientes.values())[:12])))

    def _iconos_de(self, url):
        """{id_en_la_guia: url_del_logotipo} leyendo solo la cabecera."""
        try:
            respuesta = requests.get(url, timeout=TIMEOUT)
            respuesta.raise_for_status()
        except requests.RequestException as exc:
            self.stdout.write(self.style.ERROR(f'  no se pudo leer {url}: {exc}'))
            return {}

        datos = respuesta.content
        if datos[:2] == b'\x1f\x8b':
            datos = gzip.decompress(datos)

        iconos = {}
        for _, elemento in ET.iterparse(io.BytesIO(datos), events=('end',)):
            if elemento.tag == 'channel':
                icono = elemento.find('icon')
                if icono is not None and icono.get('src'):
                    iconos[elemento.get('id', '')] = icono.get('src')
                elemento.clear()
            elif elemento.tag == 'programme':
                break

        return iconos
