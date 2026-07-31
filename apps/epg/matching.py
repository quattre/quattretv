"""
Emparejar nuestros canales con los de una fuente XMLTV.

Cada proveedor nombra los canales a su manera: TDTChannels pone `Telecinco.TV`,
open-epg pone `Antena 3.es`, otros añaden `HD`. Sin normalizar esos sufijos
parece que la fuente no trae casi nada — midiendo a lo bruto salía un 12 % de
cobertura donde en realidad hay un 73 %.
"""
import difflib
import gzip
import io
import re
import unicodedata
import xml.etree.ElementTree as ET

import requests

# Sufijos que sobran al comparar. Se quitan de los dos lados, así que da igual
# que algún canal acabe de verdad en uno de ellos.
SUFIJOS = ('hd', 'fhd', 'uhd', '4k', 'sd', 'tv', 'es')

# Por debajo de esto no se da por bueno un parecido: preferimos dejar el canal
# sin guía a colgarle la de otro.
UMBRAL = 0.88


def normaliza(nombre):
    n = unicodedata.normalize('NFKD', (nombre or '').lower())
    n = ''.join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r'[^a-z0-9]', '', n)
    for sufijo in SUFIJOS:
        if n.endswith(sufijo) and len(n) > len(sufijo) + 2:
            n = n[:-len(sufijo)]
    return n


def canales_de_fuente(url, timeout=180):
    """
    Devuelve {nombre_normalizado: (id_en_la_fuente, nombre_original)}.

    Solo lee la cabecera de canales: los programas vienen después y aquí no
    hacen falta, así que se corta en cuanto aparece el primero.
    """
    respuesta = requests.get(url, timeout=timeout)
    respuesta.raise_for_status()

    datos = respuesta.content
    if url.endswith('.gz') or datos[:2] == b'\x1f\x8b':
        datos = gzip.decompress(datos)

    encontrados = {}
    for _, elemento in ET.iterparse(io.BytesIO(datos), events=('end',)):
        if elemento.tag == 'channel':
            identificador = elemento.get('id', '')
            for nombre in elemento.findall('display-name'):
                if nombre.text and nombre.text.strip():
                    encontrados.setdefault(
                        normaliza(nombre.text), (identificador, nombre.text.strip())
                    )
            elemento.clear()
        elif elemento.tag == 'programme':
            break

    return encontrados


def emparejar(nombre_canal, disponibles, umbral=UMBRAL):
    """
    Busca el canal en la fuente. Devuelve (id, nombre_en_la_fuente, exacto).

    Devuelve None si no hay nada suficientemente parecido.
    """
    clave = normaliza(nombre_canal)
    if not clave:
        return None

    if clave in disponibles:
        identificador, original = disponibles[clave]
        return identificador, original, True

    parecidos = difflib.get_close_matches(clave, list(disponibles), n=1, cutoff=umbral)
    if parecidos:
        identificador, original = disponibles[parecidos[0]]
        return identificador, original, False

    return None
