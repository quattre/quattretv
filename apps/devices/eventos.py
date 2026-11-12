"""
Ordenes que se le mandan a un aparato desde el panel: recargar el portal o
reiniciarlo.

El aparato no se puede llamar: es el quien pregunta. Ya lo hace cada minuto
(el latido del portal, type=watchdog), asi que la orden se deja en la cache y
se le entrega en su siguiente latido. Si esta apagado, la recoge al encender
mientras no caduque.

Para recargar todos los decos de golpe (tras cambiar el portal, por ejemplo)
no se apunta una orden por aparato: se guarda la hora de la recarga general, y
cada deco cuyo portal se cargo antes de esa hora se recarga. El portal manda
en cada latido cuando se cargo.
"""
import time

from django.core.cache import cache

EVENTOS = {
    'recargar': 'Recargar el portal',
    'reiniciar': 'Reiniciar el aparato',
    # En reposo (gSTB.StandBy): el deco apaga la imagen y se enciende con el
    # mando. Solo decos: las teles no dejan apagarse desde una app.
    'apagar': 'Apagar el deco (reposo)',
}
CADUCA = 24 * 3600
CLAVE_GENERAL = 'evento:recarga_general'
# Solo los decos: las apps de las teles estan en revision y no se tocan.
TIPOS_RECARGA_GENERAL = ('mag',)


def _clave(device):
    return f'evento:aparato:{device.id}'


def pedir(device, evento):
    """True si la orden queda apuntada; False si la cache no responde."""
    if evento not in EVENTOS:
        raise ValueError(evento)
    try:
        cache.set(_clave(device), evento, CADUCA)
    except Exception:
        return False
    return True


def pedir_mensaje(device, titulo, texto):
    """Un aviso que el aparato enseña en pantalla hasta que se pulse una tecla."""
    try:
        cache.set(_clave(device), {'tipo': 'mensaje', 'titulo': titulo[:80],
                                   'texto': texto[:500]}, CADUCA)
    except Exception:
        return False
    return True


def pedir_firmware(device, url, instalar=False):
    """
    Que un deco compruebe (y si `instalar`, instale) el firmware de `url`.

    Sirve para probar un firmware nuevo en un deco concreto sin tocar la
    direccion de actualizacion automatica, que la comparten todos los decos de
    ese modelo. El deco cuenta al registro (DIAG firmware ...) lo que ve: si la
    firma y el modelo valen, y que version trae. Solo instala si la
    comprobacion sale bien.
    """
    try:
        cache.set(_clave(device), {'tipo': 'firmware', 'url': url,
                                   'instalar': bool(instalar)}, CADUCA)
        cache.set(_clave_prueba(device), {
            'url': url, 'lineas': [], 'fase': 'pedida', 'instalar': bool(instalar),
            'texto': ('Instalar' if instalar else 'Leer la imagen') +
                     ': pedido. El deco lo recoge en su siguiente latido (menos de un minuto si esta encendido).'},
            CADUCA * 7)
    except Exception:
        return False
    return True


# Las imagenes de firmware que hay publicadas, por modelo: estan en el
# servidor viejo (/var/www/firmware de 185.25.27.50, servido por su web) y son
# las firmadas para Quattre. Medido el 11/11/2026. El MAG420 no tiene.
FIRMWARE_BASE = 'http://185.25.27.50/firmware/'
FIRMWARES = {
    'MAG256': ('256/imageupdate', 218, '31/12/2022'),
    'MAG322': ('322/imageupdate', 201, '31/07/2019'),
    'MAG324': ('322/imageupdate', 201, '31/07/2019'),
    'MAG520': ('520/imageupdate', 220, '09/01/2023'),
    'MAG524': ('524/imageupdate', 207, '14/02/2023'),
    'MAG540': ('540/imageupdate', 208, '04/06/2024'),
}


def firmware_para(device):
    """{'url', 'version', 'fecha', 'actual', 'nuevo'} para la ficha del panel, o None."""
    modelo = (device.model or '').upper().replace(' ', '')
    clave = next((k for k in FIRMWARES if modelo.startswith(k)), None)
    if not clave:
        return None
    ruta, version, fecha = FIRMWARES[clave]
    import re
    # Sin el modelo pegado ("2.20.05-256", "2.20.08-pub-540"): ese 256 no es
    # la version, y hacia decir "ya lo tiene" a un 256 que no la tiene.
    fw = re.sub(r'-(?:pub-)?\d{3}\b', '', device.firmware_version or '')
    m = re.search(r'(?<![\d.:])(\d{3})(?![\d.:])', fw)
    actual = int(m.group(1)) if m else None
    return {'url': FIRMWARE_BASE + ruta, 'version': version, 'fecha': fecha, 'actual': actual,
            'nuevo': actual is not None and actual < version}


# Las imagenes de prueba: en iptv2, en media/ayuda/fw-prueba/<modelo>-<lo que
# sea>/imageupdate, por http (el actualizador del deco no abre https y esa
# carpeta es la unica de /media/ que nginx da tambien por http).
CARPETA_PRUEBAS = 'ayuda/fw-prueba'


def imagenes_para(device):
    """[(url, nombre)] de las de prueba de su modelo, las transicionales primero."""
    import os
    import re
    from django.conf import settings
    m = re.search(r'(\d{3})', (device.model or '').upper())
    if not m:
        return []
    carpeta = os.path.join(str(settings.MEDIA_ROOT), CARPETA_PRUEBAS)
    try:
        nombres = sorted(n for n in os.listdir(carpeta) if n.startswith(m.group(1) + '-')
                         and os.path.isfile(os.path.join(carpeta, n, 'imageupdate')))
    except OSError:
        return []
    host = settings.QUATTRETV.get('PUBLIC_URL', '').split('://')[-1].rstrip('/')
    nombres.sort(key=lambda n: ('trans' not in n, n))
    return [('http://%s/media/%s/%s/imageupdate' % (host, CARPETA_PRUEBAS, n), n) for n in nombres]


# ---------- Lo que cuenta el deco al probar un firmware ----------
#
# El portal manda al registro cada paso ("DIAG firmware ..."): aqui se va
# apuntando en que punto esta la prueba y que quiere decir, para enseñarlo en
# la ficha del deco sin tener que leer el registro.
#
# Ojo con lo que aprendimos el 05/11/2026: la comprobacion (startCheck) solo
# lee la imagen, NO mira la firma; un deco con el firmware de Infomir lee bien
# hasta la transicional. La firma la mira el actualizador al empezar: si no
# vale se para en 17 ("Wrong signature") al 0 % sin escribir nada.

def _clave_prueba(device):
    return f'firmware:prueba:{device.id}'


def _clave_equipo(device):
    return f'firmware:equipo:{device.id}'


def prueba_de(device):
    try:
        return cache.get(_clave_prueba(device))
    except Exception:
        return None


def equipo_de(device):
    try:
        return cache.get(_clave_equipo(device))
    except Exception:
        return None


def que_lleva(desc):
    """Lo que dice la descripcion de la imagen instalada (GetDeviceImageDesc)."""
    d = (desc or '').lower()
    if 'trans' in d:
        return 'Lleva la transicional: ya acepta las finales firmadas para Quattre.'
    if 'final' in d:
        return 'Lleva una final de operador. Si acepta nuestra firma se sabe al instalar (si no, se para al 0 % sin tocar nada).'
    if d:
        return 'No lleva ni transicional ni final de operador: con el firmware de fabrica solo entra la transicional por USB.'
    return ''


def apuntar_equipo(device, fw, desc):
    """Al arrancar: que firmware lleva. Si habia una instalacion en marcha, si ha entrado."""
    from django.utils import timezone
    try:
        antes = cache.get(_clave_equipo(device)) or {}
        cache.set(_clave_equipo(device), {'fw': fw, 'desc': desc, 'cuando': timezone.now().isoformat()},
                  90 * 86400)
        prueba = cache.get(_clave_prueba(device))
        if prueba and prueba.get('fase') in ('escribiendo', 'escrita'):
            if (fw, desc) != (antes.get('fw'), antes.get('desc')):
                _fase(prueba, 'instalada', 'Instalada: ha arrancado con %s (%s).' % (fw or '?', desc or 'sin descripcion'))
            else:
                _fase(prueba, 'error', 'Se ha reiniciado pero sigue con el mismo firmware (%s).' % (fw or '?'))
            cache.set(_clave_prueba(device), prueba, CADUCA * 7)
    except Exception:
        pass


def en_marcha(prueba):
    """Si la prueba aun puede cambiar (la ficha se recarga sola mientras)."""
    fase = (prueba or {}).get('fase')
    return fase in ('pedida', 'leyendo', 'instalando', 'escribiendo', 'escrita') or \
        (fase == 'leida' and prueba.get('instalar'))


def _fase(prueba, fase, texto):
    prueba['fase'], prueba['texto'] = fase, texto


def apuntar_prueba(device, linea):
    """Una linea "firmware ..." del portal: en que punto esta la prueba."""
    import re
    from django.utils import timezone
    ahora = timezone.localtime()
    try:
        prueba = cache.get(_clave_prueba(device)) or {}
    except Exception:
        return
    linea = linea[len('firmware '):]
    if linea.startswith('inicio') or not prueba:
        m = re.search(r'url=(\S+)', linea)
        prueba = {'url': m.group(1) if m else '', 'lineas': [], 'instalar': prueba.get('instalar')}
        _fase(prueba, 'leyendo', 'Leyendo la imagen...')
    prueba['lineas'] = (prueba.get('lineas') or [])[-14:] + [ahora.strftime('%H:%M:%S ') + linea[:200]]
    prueba['cuando'] = ahora.isoformat()
    fase = prueba.get('fase')
    if linea.startswith('sin stbUpdate'):
        _fase(prueba, 'error', 'Este aparato no deja actualizar el firmware desde el portal.')
    elif linea.startswith('error'):
        _fase(prueba, 'error', 'El deco ha dado un error: ' + linea)
    elif linea.startswith('comprobado'):
        m = re.search(r'estado=(\d+) \((.*?)\) version=(\S*) desc=(.*?) fecha=(.*)$', linea)
        estado, texto, version, desc, fecha = m.groups() if m else ('', '', '', '', '')
        if version and estado in ('21', '24'):
            # Las lineas pueden llegar desordenadas (cada una la atiende un
            # proceso): si ya esta instalando, esta no le hace volver atras.
            if fase in ('instalando', 'escribiendo', 'escrita', 'rechazada', 'parada'):
                pass
            else:
                _fase(prueba, 'leida', 'Imagen leida y de su modelo: version %s ("%s", %s). La firma se mira al instalar.'
                      % (version, desc, fecha.strip()))
        else:
            _fase(prueba, 'error', 'No ha podido leer la imagen: %s' % (texto or 'estado ' + estado))
    elif linea.startswith('instalando'):
        _fase(prueba, 'instalando', 'Instalando: el deco esta mirando la firma...')
    elif linea.startswith('progreso'):
        m = re.match(r'progreso (\d+) (\d+)%', linea)
        estado, pct = (int(m.group(1)), int(m.group(2))) if m else (-1, 0)
        if estado == 17:
            _fase(prueba, 'rechazada', 'Firma rechazada (Wrong signature), al 0 %: no se ha escrito nada. '
                  'Este deco no tiene la clave con la que esta firmada la imagen: hay que cargarle la transicional por USB.')
        elif estado == 21 and pct == 0 and (fase == 'instalando' or (fase == 'leida' and prueba.get('instalar'))):
            _fase(prueba, 'parada', 'El actualizador no arranca. Suele ser que en la tele sigue abierta la ventana '
                  'de un intento anterior: pulsa Exit en el mando y vuelve a probar.')
        elif pct >= 100:
            _fase(prueba, 'escrita', 'Escrita al 100 %: el deco se reinicia solo. Al arrancar se vera aqui si ha entrado.')
        elif pct > 0:
            _fase(prueba, 'escribiendo', 'Escribiendo: %d %%. No apagues el deco.' % pct)
    try:
        cache.set(_clave_prueba(device), prueba, CADUCA * 7)
    except Exception:
        pass


# Variables del deco que se pueden cambiar desde aqui: las que hacen falta
# para arreglar uno a distancia. El resto no se toca.
ENTORNO_PERMITIDO = ('tvsystem', 'graphicres', 'portal1', 'portal2')


def pedir_entorno(device, variables, reiniciar=False):
    """
    Cambiar variables del deco (gSTB.SetEnv) y, si se pide, reiniciarlo.

    Hizo falta con un 322 que tras actualizar el firmware salio en 576i: el
    monitor no lo enseñaba y sin imagen no se podia entrar en sus ajustes.
    """
    variables = {k: str(v) for k, v in variables.items() if k in ENTORNO_PERMITIDO}
    if not variables:
        return False
    try:
        cache.set(_clave(device), {'tipo': 'entorno', 'variables': variables,
                                   'reiniciar': bool(reiniciar)}, CADUCA)
    except Exception:
        return False
    return True


def pedir_recarga_general():
    try:
        cache.set(CLAVE_GENERAL, int(time.time()), CADUCA * 7)
    except Exception:
        return False
    return True


def recoger(device, cargado=None):
    """
    La orden pendiente para este aparato, o None. Se entrega una sola vez.
    Es el nombre de la orden o, si es un mensaje, un diccionario con el texto.
    """
    try:
        evento = cache.get(_clave(device))
        if evento:
            cache.delete(_clave(device))
            return evento
        general = cache.get(CLAVE_GENERAL)
    except Exception:
        return None
    if (general and cargado and device.device_type in TIPOS_RECARGA_GENERAL
            and int(cargado) < int(general)):
        return 'recargar'
    return None
