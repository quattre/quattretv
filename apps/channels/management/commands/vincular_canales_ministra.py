"""
Une cada canal con su equivalente en Ministra.

Ministra numera sus canales por dentro con un id que no tiene nada que ver con
el numero que ve el cliente (ninguno de los 66 coincide), y con ese id estan
guardados el archivo de storage1 y las grabaciones de los clientes. Esta orden
los empareja por nombre y enseña la tabla para revisarla: son pocos y un error
aqui significa catchup de otro canal. Por numero no se empareja nunca, porque
las dos plataformas tienen la parrilla ordenada distinto.

Solo lee de Ministra.
"""
import difflib
import re
import unicodedata

from django.core.management.base import BaseCommand, CommandError

from apps.channels.models import Channel
from apps.core import ministra


# Nombres que no se parecen en nada y son el mismo canal.
ALIAS = {
    'tdp': 'teledeporte',
    'discoverymax': 'discovery',
    'nationalgeographicwild': 'natgeowild',
    'darkxxx': 'darkconx',
}


def normalizar(nombre):
    """'7 Valencia Televisión' y '7 Valencia TV' tienen que salir iguales."""
    texto = unicodedata.normalize('NFKD', nombre or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r'\(.*?\)', '', texto)
    texto = re.sub(r'\b(hd|fhd|uhd|4k|sd|tv|television|channel|canal)\b', '', texto)
    texto = re.sub(r'[^a-z0-9]', '', texto)
    texto = re.sub(r'(?<=.)tv$', '', texto)
    return ALIAS.get(texto, texto)


def emparejar(viejos, canales):
    """
    {ministra_id: (canal, como)} para los que se encuentran.

    Va de lo seguro a lo dudoso, y lo dudoso solo entre los canales que nadie ha
    cogido todavia: si no, 'Squirrel dos' se quedaria con el 'Squirrel' que ya
    es de otro.
    """
    libres = {normalizar(c.name): c for c in canales}
    parejas = {}

    for viejo in viejos:
        clave = normalizar(viejo['name'])
        if clave in libres:
            parejas[int(viejo['id'])] = (libres.pop(clave), 'por nombre')

    for viejo in viejos:
        mid = int(viejo['id'])
        if mid in parejas:
            continue
        clave = normalizar(viejo['name'])
        if len(clave) < 3:
            continue
        prefijos = [k for k in libres if len(k) >= 3 and (clave.startswith(k) or k.startswith(clave))]
        if len(prefijos) == 1:
            parejas[mid] = (libres.pop(prefijos[0]), 'parecido (revisar)')
            continue
        parecido = difflib.get_close_matches(clave, list(libres), n=1, cutoff=0.85)
        if parecido:
            parejas[mid] = (libres.pop(parecido[0]), 'parecido (revisar)')

    return parejas


class Command(BaseCommand):
    help = 'Rellena Channel.ministra_id emparejando con los canales de Ministra'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true',
                            help='Enseñar la tabla sin guardar nada')
        parser.add_argument('--sobrescribir', action='store_true',
                            help='Rehacer tambien los que ya estan unidos')
        parser.add_argument('--fijar', action='append', default=[],
                            metavar='MINISTRA_ID=NUMERO',
                            help='Forzar una pareja a mano, p. ej. --fijar 17=5')

    def handle(self, *args, **options):
        try:
            viejos = ministra.consultar(
                'SELECT id, number, name, status FROM itv ORDER BY number')
        except ministra.MinistraError as exc:
            raise CommandError(str(exc))

        forzados = {}
        for pareja in options['fijar']:
            try:
                mid, numero = (int(x) for x in pareja.split('='))
            except ValueError:
                raise CommandError(f'--fijar {pareja}: se espera MINISTRA_ID=NUMERO')
            forzados[mid] = numero

        canales = list(Channel.objects.filter(is_radio=False))
        por_numero = {canal.number: canal for canal in canales}
        ya_usados = {c.ministra_id: c for c in canales if c.ministra_id}
        if options['sobrescribir']:
            ya_usados = {}
        sueltos = [c for c in canales if c not in ya_usados.values()]
        parejas = emparejar(
            [v for v in viejos if int(v['id']) not in ya_usados and int(v['id']) not in forzados],
            sueltos)

        unidos = sin_pareja = sin_cambios = 0
        self.stdout.write(f'{"Ministra":>8}  {"nº":>3}  {"nombre en Ministra":<28} ->  canal nuevo')
        for viejo in viejos:
            mid = int(viejo['id'])
            if mid in forzados:
                canal, como = por_numero.get(forzados[mid]), 'a mano'
            elif mid in ya_usados:
                canal, como = ya_usados[mid], 'ya estaba'
            else:
                canal, como = parejas.get(mid, (None, ''))

            apagado = '' if viejo['status'] == '1' else ' [apagado en Ministra]'
            if canal is None:
                sin_pareja += 1
                self.stdout.write(self.style.WARNING(
                    f'{mid:>8}  {viejo["number"]:>3}  {viejo["name"][:28]:<28} ->  SIN PAREJA{apagado}'))
                continue

            self.stdout.write(
                f'{mid:>8}  {viejo["number"]:>3}  {viejo["name"][:28]:<28} ->  '
                f'{canal.number} {canal.name} ({como}){apagado}')

            if canal.ministra_id == mid:
                sin_cambios += 1
                continue
            if options['simular']:
                unidos += 1
                continue
            # El campo es unico: si otro canal tenia este id, se le quita.
            Channel.objects.filter(ministra_id=mid).exclude(pk=canal.pk).update(ministra_id=None)
            canal.ministra_id = mid
            canal.save(update_fields=['ministra_id'])
            unidos += 1

        verbo = 'Se unirían' if options['simular'] else 'Unidos'
        self.stdout.write(self.style.SUCCESS(
            f'{verbo}: {unidos} · sin cambios: {sin_cambios} · sin pareja: {sin_pareja}'))
        if sin_pareja:
            self.stdout.write('Los que no tienen pareja se unen con --fijar MINISTRA_ID=NUMERO.')
