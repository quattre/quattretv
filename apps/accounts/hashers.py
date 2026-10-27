"""
Contraseñas copiadas de Ministra.

Ministra guarda md5(md5(contraseña) + id de la cuenta). Se importan tal cual,
con el id delante para poder rehacer la cuenta, y Django las pasa solo a su
formato propio la primera vez que el cliente entra con la buena: este hasher
va detras del de por defecto en PASSWORD_HASHERS, asi que nunca se usa para
guardar una contraseña nueva.
"""
import hashlib

from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.crypto import constant_time_compare


class MinistraPasswordHasher(BasePasswordHasher):
    algorithm = 'ministra'

    @staticmethod
    def calcular(password, cuenta_id):
        primero = hashlib.md5(password.encode()).hexdigest()
        return hashlib.md5(f'{primero}{cuenta_id}'.encode()).hexdigest()

    def salt(self):
        # La "sal" es el id de la cuenta en Ministra; nunca se genera aqui.
        return ''

    def encode(self, password, salt):
        assert salt and str(salt).isdigit()
        return f'{self.algorithm}${salt}${self.calcular(password, salt)}'

    def decode(self, encoded):
        algorithm, salt, hash_ = encoded.split('$', 2)
        assert algorithm == self.algorithm
        return {'algorithm': algorithm, 'salt': salt, 'hash': hash_}

    def verify(self, password, encoded):
        datos = self.decode(encoded)
        return constant_time_compare(
            self.calcular(password, datos['salt']), datos['hash'])

    def safe_summary(self, encoded):
        datos = self.decode(encoded)
        return {'algorithm': datos['algorithm'], 'salt': datos['salt'],
                'hash': mask_hash(datos['hash'])}

    def must_update(self, encoded):
        return True

    def harden_runtime(self, password, encoded):
        pass
