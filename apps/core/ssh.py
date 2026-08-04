"""
Localizar el binario de ssh.

El servicio web arranca con `PATH=/var/www/quattretv/venv/bin` y nada más, así
que llamar a "ssh" a secas falla con "no se pudo ejecutar ssh" aunque desde una
consola funcione perfectamente. Se busca por ruta absoluta.
"""
import os
import shutil

RUTAS = ('/usr/bin/ssh', '/bin/ssh', '/usr/local/bin/ssh')


def ssh_bin():
    encontrado = shutil.which('ssh')
    if encontrado:
        return encontrado
    for ruta in RUTAS:
        if os.path.exists(ruta):
            return ruta
    # Que falle con un mensaje claro y no con un PATH silencioso.
    return 'ssh'
