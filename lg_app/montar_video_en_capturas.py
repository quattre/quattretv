#!/usr/bin/env python3
"""
Mete la imagen real del canal en el hueco negro de las capturas.

Por que hace falta: en un televisor el video no lo pinta el navegador, va en un
plano de hardware aparte. Asi que cuando se le pide una captura a la app, la
interfaz sale perfecta y donde deberia verse el canal sale negro. Esto no tiene
arreglo desde el lado del navegador.

Lo que hace esto: coge un fotograma de verdad del canal — bajado del CDN, el
mismo que esta viendo el televisor — y lo pone donde le toca. El resultado es la
interfaz real con contenido real, a 1920x1080, que es exactamente lo que se ve
en la television.

El hueco no se adivina: sale de la misma constante que usa el portal para
colocar el video (HUECO en portal.html), asi que si algun dia se cambia el
reparto de la pantalla, se cambia aqui el mismo numero y ya esta.

    python3 lg_app/montar_video_en_capturas.py <carpeta> <fotograma.png>
"""
import os
import sys

from PIL import Image, ImageChops, ImageDraw

# Las mismas proporciones que HUECO en templates/stb/portal.html.
HUECO = {'x': 0.390, 'y': 0.111, 'ancho': 0.589, 'alto': 0.589}
REDONDEO = 14           # el border-radius del video en el portal
NEGRO_MAXIMO = 6        # por debajo de esto se considera hueco de video


def rectangulo(ancho, alto):
    return (
        round(ancho * HUECO['x']),
        round(alto * HUECO['y']),
        round(ancho * HUECO['ancho']),
        round(alto * HUECO['alto']),
    )


def esquinas_redondeadas(im, radio):
    mascara = Image.new('L', im.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [(0, 0), (im.size[0] - 1, im.size[1] - 1)], radius=radio, fill=255)
    return mascara


def mascara_de_negro(im):
    """Blanco donde hay interfaz, negro donde el televisor pondria el video."""
    r, g, b = im.split()
    mayor = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return mayor.point(lambda v: 0 if v <= NEGRO_MAXIMO else 255)


def es_pantalla_completa(captura):
    """
    En pantalla completa el video ocupa todo; en las demas pantallas hay un
    panel de interfaz a la izquierda.

    No vale contar el negro de toda la imagen: en cualquier pantalla la mitad
    derecha ya es negra, asi que todas parecerian pantalla completa. Lo que las
    distingue es si ese panel esta o no.
    """
    ancho, alto = captura.size
    panel = captura.crop((int(ancho * 0.03), int(alto * 0.10),
                          int(ancho * 0.36), int(alto * 0.85)))
    pintado = mascara_de_negro(panel).convert('L')
    blancos = sum(pintado.resize((120, 120)).point(lambda v: 1 if v else 0).getdata())
    return blancos < (120 * 120) * 0.5


def montar(ruta_captura, fotograma, destino):
    captura = Image.open(ruta_captura).convert('RGB')
    ancho, alto = captura.size

    if es_pantalla_completa(captura):
        # El fondo pasa a ser el canal, y encima se vuelve a poner la interfaz
        # respetando solo lo que no era negro: la barra del canal y su texto.
        fondo = fotograma.resize((ancho, alto), Image.LANCZOS)
        fondo.paste(captura, (0, 0), mascara_de_negro(captura))
        fondo.save(destino)
        return 'pantalla completa'

    x, y, w, h = rectangulo(ancho, alto)
    trozo = fotograma.resize((w, h), Image.LANCZOS)
    captura.paste(trozo, (x, y), esquinas_redondeadas(trozo, REDONDEO))
    captura.save(destino)
    return 'hueco de %dx%d en (%d, %d)' % (w, h, x, y)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    carpeta, ruta_fotograma = sys.argv[1], sys.argv[2]
    salida = os.path.join(carpeta, 'con-video')
    os.makedirs(salida, exist_ok=True)

    fotograma = Image.open(ruta_fotograma).convert('RGB')
    print('Fotograma del canal: %dx%d' % fotograma.size)
    print()

    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.endswith('.png'):
            continue
        destino = os.path.join(salida, nombre)
        que = montar(os.path.join(carpeta, nombre), fotograma, destino)
        print('  %-20s %s' % (nombre, que))

    print()
    print('Montadas en %s/' % salida)


if __name__ == '__main__':
    main()
