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
    # Solo lee los bancos de firmware y los ajustes de arranque, al registro.
    'diagnostico': 'Contar bancos y ajustes de arranque',
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


# Las imagenes de firmware que hay publicadas, por modelo: son las firmadas
# para Quattre. Medido el 11/11/2026. El MAG420 no tiene. Estaban en el
# servidor viejo (185.25.27.50); desde el 20/11/2026 las sirve iptv2 en
# /var/www/firmware, con el mismo nombre que llevan los decos en update_url.
FIRMWARE_BASE = 'http://iptv1.quattre.com/firmware/'
FIRMWARES = {
    'MAG256': ('256/imageupdate', 218, '31/12/2022'),
    'MAG322': ('322/imageupdate', 201, '31/07/2019'),
    'MAG324': ('322/imageupdate', 201, '31/07/2019'),
    'MAG520': ('520/imageupdate', 220, '09/01/2023'),
    'MAG524': ('524/imageupdate', 207, '14/02/2023'),
    'MAG540': ('540/imageupdate', 208, '04/06/2024'),
}


def firmware_para(device):
    """
    Para la ficha y el listado del panel: que version lleva el deco y cual es
    la ultima final que tenemos para su modelo.

    {'version', 'fecha', 'url', 'actual', 'desc', 'nuevo', 'al_dia'} o None si
    no hay ninguna imagen final para ese modelo.

    Antes se comparaba con la tabla FIRMWARES (lo publicado en Ministra, la
    208 del 540) y con un numero sacado del texto de compilacion, que no lo
    lleva: un 540 con la 213 no decia ni que version tenia ni que era la ultima.
    """
    ultima = _ultima_final(imagenes_para(device))
    if not ultima:
        return None
    equipo = equipo_de(device) or {}
    return _comparar(ultima, equipo)


def _ultima_final(imagenes):
    finales = [i for i in imagenes if not i['transicional'] and str(i['version']).isdigit()]
    if not finales:
        return None
    # A igual version, la de la clave normal antes que la de la clave de 2021.
    return max(finales, key=lambda i: (int(i['version']), 'clave' not in i['nombre']))


def _comparar(ultima, equipo):
    actual = equipo.get('version')
    version = int(ultima['version'])
    return {'url': ultima['url'], 'version': version, 'fecha': ultima['fecha'],
            'actual': actual, 'desc': equipo.get('desc', ''),
            'nuevo': actual is not None and actual < version,
            'al_dia': actual is not None and actual >= version}


def firmware_de_lista(devices):
    """
    Lo mismo que firmware_para, para muchos decos de una vez (el listado):
    {id: {...}}. Lee las imagenes una vez por modelo y la cache de un golpe.
    """
    por_prefijo, salida = {}, {}
    decos = [d for d in devices if d.device_type == 'mag']
    try:
        equipos = cache.get_many([_clave_equipo(d) for d in decos])
    except Exception:
        equipos = {}
    for d in decos:
        pre = _prefijo(d)
        if pre not in por_prefijo:
            por_prefijo[pre] = _ultima_final(imagenes_para(d)) if pre else None
        equipo = equipos.get(_clave_equipo(d)) or {}
        if por_prefijo[pre]:
            salida[d.id] = _comparar(por_prefijo[pre], equipo)
        elif equipo.get('version') is not None:
            salida[d.id] = {'version': None, 'actual': equipo['version'], 'desc': equipo.get('desc', ''),
                            'nuevo': False, 'al_dia': False}
    return salida


# El 322 lleva la imagen del 324 (son la misma familia y la carpeta se llama 324-...).
FAMILIA_IMAGEN = {'322': '324'}


def _prefijo(device):
    import re
    m = re.search(r'(\d{3})', (device.model or '').upper())
    return FAMILIA_IMAGEN.get(m.group(1), m.group(1)) if m else ''


# Las imagenes de prueba: en iptv2, en media/ayuda/fw-prueba/<modelo>-<lo que
# sea>/imageupdate, por http (el actualizador del deco no abre https y esa
# carpeta es la unica de /media/ que nginx da tambien por http).
CARPETA_PRUEBAS = 'ayuda/fw-prueba'


def imagenes_para(device):
    """Las de prueba de su modelo, con lo que dice su cabecera, la mas nueva primero."""
    import os
    import re
    from django.conf import settings
    prefijo = _prefijo(device)
    if not prefijo:
        return []
    carpeta = os.path.join(str(settings.MEDIA_ROOT), CARPETA_PRUEBAS)
    try:
        nombres = sorted(n for n in os.listdir(carpeta) if n.startswith(prefijo + '-')
                         and os.path.isfile(os.path.join(carpeta, n, 'imageupdate')))
    except OSError:
        return []
    host = settings.QUATTRETV.get('PUBLIC_URL', '').split('://')[-1].rstrip('/')
    datos = {n: cabecera_imagen(os.path.join(carpeta, n, 'imageupdate')) for n in nombres}
    # La mas nueva arriba, por la fecha de montaje que lleva la propia imagen.
    nombres.sort(key=lambda n: datos[n]['orden'], reverse=True)
    return [dict(datos[n], nombre=n, transicional='trans' in (datos[n]['desc'] + n).lower(),
                 url='http://%s/media/%s/%s/imageupdate' % (host, CARPETA_PRUEBAS, n)) for n in nombres]


def cabecera_imagen(ruta):
    """
    Lo que la imagen dice de si misma en su cabecera (texto, al principio):
    version, descripcion y fecha de montaje. El nombre de la carpeta lo pone
    quien la sube y no bastaba para saber cual era cual.
    """
    from datetime import datetime
    import re
    c = {}
    try:
        with open(ruta, 'rb') as f:
            for linea in f.read(600).decode('latin1').split('Start data')[0].splitlines():
                k, _, v = linea.partition(':')
                c[k.strip()] = v.strip()
    except OSError:
        pass
    fecha = None
    # "Fri Nov 13 12:23:23 CET 2026": sin el dia de la semana ni la zona.
    m = re.match(r'\w+ (\w+) +(\d+) (\d+:\d+):\d+ \w+ (\d{4})', c.get('Date', ''))
    if m:
        try:
            fecha = datetime.strptime('%s %s %s %s' % m.groups(), '%b %d %H:%M %Y')
        except ValueError:
            pass
    return {'version': c.get('Image Version', ''), 'desc': c.get('Image Description', ''),
            'fecha': fecha.strftime('%d/%m/%Y %H:%M') if fecha else '', 'orden': fecha or datetime.min}


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


def apuntar_version(device, version, desc=None):
    """La version de la imagen instalada (Image_Version), cuando el deco la dice."""
    try:
        version = int(version)
        equipo = cache.get(_clave_equipo(device)) or {}
        equipo['version'] = version
        if desc is not None:
            equipo['desc'] = desc
        cache.set(_clave_equipo(device), equipo, 90 * 86400)
    except Exception:
        pass


def apuntar_equipo(device, fw, desc, version=None):
    """Al arrancar: que firmware lleva. Si habia una instalacion en marcha, si ha entrado."""
    from django.utils import timezone
    try:
        antes = cache.get(_clave_equipo(device)) or {}
        equipo = {'fw': fw, 'desc': desc, 'cuando': timezone.now().isoformat()}
        if version is not None:
            equipo['version'] = version
        elif (fw, desc) == (antes.get('fw'), antes.get('desc')) and antes.get('version') is not None:
            # Los portales viejos no mandan la version: si arranca con lo
            # mismo, vale la que ya se sabia; si ha cambiado, no se sabe.
            equipo['version'] = antes['version']
        cache.set(_clave_equipo(device), equipo, 90 * 86400)
        prueba = cache.get(_clave_prueba(device))
        if prueba and prueba.get('fase') in ('escribiendo', 'escrita'):
            if (fw, desc) != (antes.get('fw'), antes.get('desc')):
                _fase(prueba, 'instalada', 'Instalada: ha arrancado con %s (%s).' % (fw or '?', desc or 'sin descripcion'))
            elif prueba.get('fase') == 'escrita':
                # Llego al 100 % y arranca igual: era la misma que ya tenia
                # (el 12/11 se reinstalo la final de 2022 en un 256 que la llevaba).
                _fase(prueba, 'instalada', 'Instalada al 100 %%. Arranca con %s (%s), lo mismo que llevaba: '
                      'era la misma version.' % (fw or '?', desc or 'sin descripcion'))
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
    # Las lineas llegan casi a la vez y cada una la atiende un proceso: sin
    # turno, "estados 21" pisaba a "comprobado" y la ficha se quedaba para
    # siempre en "Leyendo la imagen...".
    cerrojo = _clave_prueba(device) + ':turno'
    import time
    for _ in range(20):
        try:
            if cache.add(cerrojo, 1, 5):
                break
        except Exception:
            return
        time.sleep(0.05)
    try:
        _apuntar_prueba(device, linea, ahora)
    finally:
        try:
            cache.delete(cerrojo)
        except Exception:
            pass


def _apuntar_prueba(device, linea, ahora):
    import re
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


def pedir_diagnostico(device, variables):
    """Que el deco cuente al registro estas variables suyas (solo las lee)."""
    variables = [str(v) for v in variables if str(v).replace('_', '').isalnum()][:40]
    try:
        cache.set(_clave(device), {'tipo': 'diagnostico', 'variables': variables}, CADUCA)
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
