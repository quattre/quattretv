"""
Lectura de la base de datos de Ministra, la plataforma antigua.

Mientras convivan las dos plataformas, Ministra sigue mandando: aqui solo se
lee. Se entra por SSH a la maquina vieja y se lanza el mysql de alli, asi que
no hace falta abrir el puerto de MySQL ni copiar su contraseña a ningun sitio:
se lee en remoto del custom.ini, como hace la propia Ministra. Cada consulta va
dentro de una transaccion de solo lectura.

La maquina se configura con MINISTRA_SSH (usuario@host:puerto) en el .env.
"""
import base64
import os
import re
import subprocess

from apps.core.ssh import ssh_bin

MINISTRA_SSH = os.environ.get('MINISTRA_SSH', 'quattre@185.25.27.50:2101')
CUSTOM_INI = '/var/www/stalker_portal/server/custom.ini'
ESPERA = 120


class MinistraError(Exception):
    """No se pudo leer la base de datos de Ministra."""


def _destino():
    destino, _, puerto = MINISTRA_SSH.rpartition(':')
    if not destino or not puerto.isdigit():
        return MINISTRA_SSH, '22'
    return destino, puerto


# mysql --batch escapa asi los caracteres especiales de cada campo.
_ESCAPES = {'\\t': '\t', '\\n': '\n', '\\0': '\0', '\\\\': '\\'}


def _valor(campo):
    if campo == 'NULL':
        return None
    return re.sub(r'\\[tn0\\]', lambda m: _ESCAPES[m.group(0)], campo)


def consultar(sql):
    """Lanza una consulta en Ministra y devuelve una lista de diccionarios."""
    destino, puerto = _destino()
    remoto = (
        f'P=$(grep -hiE "^\\s*mysql_pass" {CUSTOM_INI} | tail -1 '
        '| sed -E "s/^[^=]*=\\s*//; s/^\\"//; s/\\"\\s*$//"); '
        'MYSQL_PWD="$P" mysql -u stalker stalker_db --batch '
        '--default-character-set=utf8'
    )
    entrada = (
        'SET SESSION TRANSACTION READ ONLY; START TRANSACTION READ ONLY;\n'
        f'{sql.rstrip().rstrip(";")};\nROLLBACK;\n'
    )
    try:
        resultado = subprocess.run(
            [ssh_bin(), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
             '-o', 'StrictHostKeyChecking=accept-new',
             '-p', puerto, destino, remoto],
            input=entrada.encode(), capture_output=True, timeout=ESPERA,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MinistraError(f'No se pudo entrar en {MINISTRA_SSH}: {exc}') from exc

    if resultado.returncode != 0:
        error = resultado.stderr.decode(errors='replace').strip()
        raise MinistraError(error or f'ssh termino con {resultado.returncode}')

    lineas = resultado.stdout.decode('utf-8', errors='replace').split('\n')
    lineas = [linea for linea in lineas if linea]
    if not lineas:
        return []
    cabecera = lineas[0].split('\t')
    return [
        dict(zip(cabecera, (_valor(c) for c in linea.split('\t'))))
        for linea in lineas[1:]
    ]


def favoritos(fav_ch):
    """
    Los favoritos de una cuenta, como lista de id de canal de Ministra.

    Ministra los guarda como un array de PHP serializado y pasado a base64
    (a:67:{i:0;s:1:"2";i:1;s:1:"3";...}). El orden es el del array.
    """
    if not fav_ch:
        return []
    try:
        crudo = base64.b64decode(fav_ch).decode('utf-8', errors='replace')
    except ValueError:
        crudo = fav_ch
    if not crudo.startswith('a:'):
        return []
    # Cada valor llega como cadena (s:2:"17") o, a veces, como entero tras su
    # clave (i:3;i:17;). Las claves son la posicion y no interesan.
    return [int(x) for x in re.findall(r'(?:s:\d+:"|i:\d+;i:)(\d+)', crudo)]


def lista_de_ids(valores):
    """'1,2,3' seguro para meter en un IN (...): solo enteros."""
    return ','.join(str(int(v)) for v in valores) or '0'
