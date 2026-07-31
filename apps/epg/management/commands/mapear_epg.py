"""
Empareja los canales con los de las fuentes EPG y rellena su epg_id.

Sin esto la guía no se llena aunque la fuente esté bien: el importador busca los
canales por `epg_id` y en la plataforma están todos vacíos. Hacerlo a mano son
83 canales mirando identificadores ajenos uno por uno.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.channels.models import Channel
from apps.epg import matching
from apps.epg.models import EpgSource


class Command(BaseCommand):
    help = 'Rellena epg_id de los canales emparejándolos con las fuentes EPG'

    def add_arguments(self, parser):
        parser.add_argument('--fuente', help='Nombre de una fuente concreta')
        parser.add_argument('--simular', action='store_true',
                            help='Enseñar lo que haría sin guardar')
        parser.add_argument('--sobrescribir', action='store_true',
                            help='Cambiar también los que ya tienen epg_id')
        parser.add_argument('--incluir-radios', action='store_true',
                            help='Las radios se saltan por defecto: no llevan guía')
        parser.add_argument('--umbral', type=float, default=matching.UMBRAL,
                            help='Cuánto parecido exigir (0-1)')

    def handle(self, *args, **options):
        fuentes = EpgSource.objects.filter(is_active=True)
        if options['fuente']:
            fuentes = fuentes.filter(name=options['fuente'])

        if not fuentes.exists():
            raise CommandError(
                'No hay fuentes EPG activas. Se dan de alta en Portal → EPG.'
            )

        canales = Channel.objects.filter(is_active=True)
        if not options['incluir_radios']:
            canales = canales.filter(is_radio=False)
        if not options['sobrescribir']:
            canales = canales.filter(epg_id='')

        pendientes = list(canales.order_by('number'))
        if not pendientes:
            self.stdout.write('Todos los canales tienen ya su epg_id.')
            return

        self.stdout.write(f'{len(pendientes)} canales por mapear\n')
        emparejados = 0

        for fuente in fuentes:
            if not pendientes:
                break

            self.stdout.write(self.style.MIGRATE_HEADING(f'\n{fuente.name}'))
            try:
                disponibles = matching.canales_de_fuente(fuente.url)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  No se pudo leer: {exc}'))
                continue

            self.stdout.write(f'  {len(disponibles)} canales en la fuente')
            quedan = []

            for canal in pendientes:
                resultado = matching.emparejar(canal.name, disponibles, options['umbral'])
                if not resultado:
                    quedan.append(canal)
                    continue

                identificador, original, exacto = resultado
                marca = '' if exacto else '  (por parecido, revisar)'
                self.stdout.write(
                    f'  {canal.number} {canal.name} -> {identificador}{marca}'
                )
                if not options['simular']:
                    canal.epg_id = identificador
                    canal.save(update_fields=['epg_id'])
                emparejados += 1

            pendientes = quedan

        self.stdout.write(self.style.SUCCESS(
            f'\n{emparejados} canales mapeados'
            + (' (simulado)' if options['simular'] else '')
        ))
        if pendientes:
            self.stdout.write(self.style.WARNING(
                f'{len(pendientes)} sin fuente: '
                + ', '.join(c.name for c in pendientes)
            ))
            self.stdout.write(
                'Esos hay que mapearlos a mano en la ficha del canal, o añadir '
                'otra fuente que los traiga.'
            )
