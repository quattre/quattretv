"""
Caratulas apaisadas para el videoclub.

Las guias traen sobre todo carteles verticales (Orange, Movistar, El Mundo,
3Cat: 804 de 2114 tarjetas el 11/11/2026) y las tarjetas son 16:9: entero
quedaba un cartel estrecho con dos franjas grises y el titulo encima. Aqui se
hace, una vez por imagen y sin nadie mirando, una version 16:9:

- Si otra guia trae una imagen horizontal del mismo titulo (Sincroguia las da
  de 1280x720), esa, recortada a 16:9.
- Si no, el cartel a la derecha y de fondo el mismo cartel ampliado,
  difuminado y oscurecido, como hacen las plataformas con los carteles.

Sale de 640x360 y unos 40 KB: tambien pesa menos que el cartel original
(los de Orange son de 720x960 y 100 KB), y eso al MAG le viene bien.

La pide la tarjeta (completar en caratulas.py) y la hace una tarea de Celery:
mientras no esta, la tarjeta sale con la imagen de la guia, como antes. Se
guardan en media/miniaturas y las sirve nginx; las que nadie pide en un mes
se borran.
"""
import hashlib
import io
import logging
import os
import time

import requests
from django.conf import settings
from django.core.cache import cache

from .semana import plano

logger = logging.getLogger(__name__)

ANCHO, ALTO = 640, 360
HORIZONTAL = 1.3            # ancho/alto a partir del cual ya es apaisada
MAX_BYTES = 8 * 1024 * 1024
DIAS = 30
CARPETA = os.path.join(str(settings.MEDIA_ROOT), 'miniaturas')
# Entera y no relativa: el MAG carga el portal por iptv1 (el proxy de la
# plataforma vieja), que no tiene /media/, y alli daban 404.
URL = settings.QUATTRETV.get('PUBLIC_URL', '').rstrip('/') + '/' + settings.MEDIA_URL.strip('/') + '/miniaturas/'
CABECERAS = {'User-Agent': 'Mozilla/5.0 (QuattreTV videoclub)'}


def _nombre(titulo, img):
    return hashlib.md5(('%s|%s' % (plano(titulo), img)).encode()).hexdigest() + '.jpg'


def poner(items):
    """
    Cambia la imagen de cada tarjeta por su version 16:9 si ya esta hecha, y
    encarga las que faltan.
    """
    faltan = []
    for i in items:
        otras = i.pop('_otras', None) or []
        img = i.get('img') or ''
        if not img or img.startswith(URL) or img.startswith('/'):
            continue
        nombre = _nombre(i.get('titulo', ''), img)
        ruta = os.path.join(CARPETA, nombre)
        try:
            tam = os.path.getsize(ruta)
        except OSError:
            tam = None
        if tam:
            # Con el tamaño en la direccion: nginx las da para 7 dias, y una
            # rehecha tiene que llegar al deco sin esperar.
            i['img'] = '%s%s?v=%d' % (URL, nombre, tam)
            try:
                os.utime(ruta)      # en uso: que limpiar() no la borre
            except OSError:
                pass
        elif cache.add('miniatura:pedida:' + nombre, 1, 6 * 3600):
            faltan.append([i.get('titulo', ''), img, otras[:6]])
    if faltan:
        from apps.epg.tasks import hacer_miniaturas
        for desde in range(0, len(faltan), 50):
            hacer_miniaturas.delay(faltan[desde:desde + 50])


def _abrir(url):
    from PIL import Image
    r = requests.get(url, headers=CABECERAS, timeout=10, stream=True)
    r.raise_for_status()
    datos = r.raw.read(MAX_BYTES + 1, decode_content=True)
    if len(datos) > MAX_BYTES:
        raise ValueError('demasiado grande')
    im = Image.open(io.BytesIO(datos))
    im.load()
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        fondo = Image.new('RGB', im.size, (29, 32, 35))
        fondo.paste(im, mask=im.split()[-1])
        return fondo
    return im.convert('RGB')


def _apaisada(im):
    from PIL import Image, ImageOps
    return ImageOps.fit(im, (ANCHO, ALTO), Image.LANCZOS, centering=(0.5, 0.35))


def _cartel(im):
    """El cartel entero a la derecha, sobre si mismo ampliado y difuminado."""
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    # Difuminar en pequeño y ampliar: el mismo efecto por una fraccion del coste.
    fondo = ImageOps.fit(im, (ANCHO // 8, ALTO // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
    fondo = ImageEnhance.Brightness(fondo.resize((ANCHO, ALTO), Image.BICUBIC)).enhance(0.55)
    alto = ALTO
    ancho = min(ANCHO, round(im.width * alto / im.height))
    cartel = im.resize((ancho, alto), Image.LANCZOS)
    fondo.paste(cartel, (ANCHO - ancho - round(ANCHO * 0.06) if ancho < ANCHO * 0.8 else (ANCHO - ancho) // 2, 0))
    return fondo


def otras_de(titulo, img, otras):
    """
    Las imagenes del mismo titulo en las guias, sin repetir y sin las de
    relleno: Sincroguia pone la misma de unas palomitas a muchas peliculas, y
    una imagen que sale con varios titulos no es de ninguno.
    """
    from apps.epg.models import Program
    vistas, salida = {img}, []
    deguias = Program.objects.filter(title__iexact=titulo).exclude(icon='') \
        .order_by().values_list('icon', flat=True).distinct()[:10]
    for u in list(otras) + list(deguias):
        if not u or u in vistas:
            continue
        vistas.add(u)
        if de_relleno(u):
            continue
        salida.append(u)
    return salida[:8]


def de_relleno(url):
    from apps.epg.models import Program
    return Program.objects.filter(icon=url).order_by().values('title').distinct().count() > 2


def hacer(titulo, img, otras=()):
    """Hace la miniatura de una tarjeta. Devuelve como ha salido."""
    nombre = _nombre(titulo, img)
    destino = os.path.join(CARPETA, nombre)
    if os.path.exists(destino):
        return 'ya'
    alternativas = otras_de(titulo, img, otras)
    # La de la guia es de relleno (la misma para muchas): mejor otra del titulo.
    origen = alternativas.pop(0) if alternativas and de_relleno(img) else img
    try:
        principal = _abrir(origen)
    except Exception as e:
        logger.info('miniatura: no se puede abrir %s (%s)', origen, e)
        return 'error'
    if principal.width / principal.height >= HORIZONTAL:
        hecha, como = _apaisada(principal), 'horizontal'
    else:
        hecha, como = None, 'cartel'
        for u in alternativas:
            try:
                im = _abrir(u)
            except Exception:
                continue
            if im.width / im.height >= HORIZONTAL and im.width >= 400:
                hecha, como = _apaisada(im), 'de otra guia'
                break
        if hecha is None:
            hecha = _cartel(principal)
    os.makedirs(CARPETA, exist_ok=True)
    temporal = destino + '.tmp'
    hecha.save(temporal, 'JPEG', quality=80, optimize=True)
    os.replace(temporal, destino)
    return como


def limpiar():
    """Borra las que llevan un mes sin salir en ninguna tarjeta (una vez al dia)."""
    if not cache.add('miniaturas:limpieza', 1, 86400) or not os.path.isdir(CARPETA):
        return 0
    limite = time.time() - DIAS * 86400
    borradas = 0
    for f in os.listdir(CARPETA):
        ruta = os.path.join(CARPETA, f)
        try:
            if os.path.getmtime(ruta) < limite:
                os.remove(ruta)
                borradas += 1
        except OSError:
            pass
    return borradas
