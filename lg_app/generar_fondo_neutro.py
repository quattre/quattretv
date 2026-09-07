#!/usr/bin/env python3
"""
Pinta la imagen abstracta que va en el hueco del video de las capturas.

Por que no se pone un fotograma real: las capturas de la tienda enseñan la
interfaz, no el contenido. Un fotograma de verdad trae encima los logotipos de
quien emite -- LaLiga, EA Sports, el mosca del canal -- y eso son marcas de
terceros en un escaparate nuestro. Ademas envejece: el titular del dia se queda
puesto meses.

Asi que va un degradado en los colores de la casa. Se ve que hay imagen, se
entiende que es un reproductor, y no se dice nada que no sea nuestro. Es lo
mismo que se hizo para LG.

    python3 lg_app/generar_fondo_neutro.py [destino.png]
"""
import sys

from PIL import Image, ImageDraw, ImageFilter

ANCHO, ALTO = 1920, 1080

# Manchas de color: (x, y, radio, color). Verde de la marca y un azul frio para
# que no quede plano, sobre carbon.
MANCHAS = [
    (620, 300, 620, (74, 122, 20)),
    (1180, 250, 540, (36, 74, 30)),
    (1500, 780, 620, (18, 52, 68)),
    (380, 860, 520, (22, 40, 26)),
    (980, 620, 420, (12, 20, 24)),
]


def generar():
    im = Image.new('RGB', (ANCHO, ALTO), (10, 14, 16))
    d = ImageDraw.Draw(im)
    for x, y, r, color in MANCHAS:
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    # El desenfoque es lo que lo convierte en un degradado y no en circulos.
    return im.filter(ImageFilter.GaussianBlur(190))


if __name__ == '__main__':
    destino = sys.argv[1] if len(sys.argv) > 1 else 'lg_app/fondo_neutro.png'
    generar().save(destino, 'PNG', optimize=True)
    print('Generado: %s' % destino)
