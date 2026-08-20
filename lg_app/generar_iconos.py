#!/usr/bin/env python3
"""
Genera el icono y la pantalla de arranque de la app de LG.

Sustituye al generate_icons.html, que habia que abrir en un navegador y
descargar a mano, y que ademas se quedo con la paleta vieja (fondo gris #2c3134
y un degradado azul que no era el de la casa).

Uso:  python3 generar_iconos.py [ruta-a-Antonio.ttf]
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, 'Antonio.ttf')

# La paleta del portal. El fondo va casi negro y no gris: en una tele los grises
# medios se ven lavados y apagan el verde.
FONDO_ALTO = (20, 27, 31)     # #141b1f
FONDO_BAJO = (8, 11, 13)      # #080b0d
VERDE      = (129, 186, 38)   # #81ba26, el de la marca
BLANCO     = (255, 255, 255)
VERDE_VIVO = (154, 214, 47)   # #9ad62f, para realces


def degradado(ancho, alto, arriba, abajo):
    img = Image.new('RGB', (ancho, alto))
    d = ImageDraw.Draw(img)
    for y in range(alto):
        t = y / max(alto - 1, 1)
        d.line([(0, y), (ancho, y)],
               fill=tuple(int(arriba[i] + (abajo[i] - arriba[i]) * t) for i in range(3)))
    return img


def centrar(d, texto, fuente, ancho):
    caja = d.textbbox((0, 0), texto, font=fuente)
    return (ancho - (caja[2] - caja[0])) // 2 - caja[0], caja


def icono(lado):
    """
    Icono cuadrado con el logotipo en dos lineas, verde sobre blanco.

    A 80 px un logotipo en una sola linea no se lee, asi que va apilado. Va
    sobre blanco a proposito: en la fila de aplicaciones de una television casi
    todos los iconos son oscuros, asi que uno blanco destaca. Y es como se ve la
    marca en quattre.com.
    """
    img = Image.new('RGB', (lado, lado), BLANCO)
    d = ImageDraw.Draw(img)

    # LG exige un minimo de 5 px de margen interior. Con 0,11 quedan 8,8 px
    # en el de 80, asi que cumple y el logotipo llena mejor la baldosa —
    # importante porque el icono no se redondea y un cuadrado blanco con
    # mucho aire se lee como si faltara la imagen.
    margen = int(lado * 0.11)
    hueco = lado - margen * 2

    # Se busca el cuerpo que hace que la palabra mas larga ocupe el ancho util.
    cuerpo = 4
    while cuerpo < lado:
        f = ImageFont.truetype(FUENTE, cuerpo + 1)
        caja = d.textbbox((0, 0), 'Quattre', font=f)
        if caja[2] - caja[0] > hueco:
            break
        cuerpo += 1

    f_arriba = ImageFont.truetype(FUENTE, cuerpo)
    f_abajo = ImageFont.truetype(FUENTE, int(cuerpo * 1.42))

    x1, c1 = centrar(d, 'Quattre', f_arriba, lado)
    x2, c2 = centrar(d, 'TV', f_abajo, lado)
    alto1, alto2 = c1[3] - c1[1], c2[3] - c2[1]
    separacion = int(lado * 0.03)
    y = (lado - (alto1 + separacion + alto2)) // 2

    d.text((x1, y - c1[1]), 'Quattre', font=f_arriba, fill=VERDE)
    d.text((x2, y + alto1 + separacion - c2[1]), 'TV', font=f_abajo, fill=VERDE)
    return esquinas_redondas(img, int(lado * 0.16))


def esquinas_redondas(img, radio):
    """
    Redondea las esquinas dejando BLANCO debajo de la transparencia.

    El primer intento las dejo con negro debajo del canal alfa, y la television
    pintaba las esquinas de negro — o sea que no estaba respetando la
    transparencia, sino enseñando lo que hubiera debajo. Con blanco debajo sale
    bien de las dos maneras: si respeta el alfa queda redondeado, y si no,
    quedan esquinas blancas en vez de negras.
    """
    mascara = Image.new('L', img.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, img.size[0] - 1, img.size[1] - 1], radius=radio, fill=255)
    salida = Image.new('RGBA', img.size, BLANCO + (0,))
    salida.paste(img, (0, 0), mascara)
    return salida


def arranque(ancho=1920, alto=1080):
    """Pantalla de arranque, con la misma cara que el splash del index.html."""
    img = degradado(ancho, alto, FONDO_ALTO, FONDO_BAJO)
    d = ImageDraw.Draw(img)

    f = ImageFont.truetype(FUENTE, 150)
    x, caja = centrar(d, 'QuattreTV', f, ancho)
    altura = caja[3] - caja[1]
    y = (alto - altura) // 2 - 40
    d.text((x, y - caja[1]), 'QuattreTV', font=f, fill=VERDE)

    # Filete verde debajo, el mismo detalle que lleva el splash del HTML.
    ancho_filete, grosor = 200, 6
    fy = y + altura + 52
    for i in range(ancho_filete):
        t = i / (ancho_filete - 1)
        col = tuple(int(VERDE[j] + (VERDE_VIVO[j] - VERDE[j]) * t) for j in range(3))
        d.rectangle([(ancho - ancho_filete) // 2 + i, fy,
                     (ancho - ancho_filete) // 2 + i, fy + grosor], fill=col)
    return img


if __name__ == '__main__':
    if not os.path.exists(FUENTE):
        sys.exit('No encuentro la fuente Antonio en %s' % FUENTE)
    # Los dos a 130. LG documenta 80 para icon.png, pero la television pinta
    # ESE en la fila de aplicaciones y a su tamaño real: al lado de los iconos
    # del sistema, que llenan la baldosa de 130, el nuestro se veia al 61 % con
    # negro alrededor — y 80/130 es justo 0,61.
    icono(130).save(os.path.join(AQUI, 'icon.png'))
    icono(130).save(os.path.join(AQUI, 'largeIcon.png'))
    # El de 400 no va dentro del paquete: se sube aparte en Seller Lounge y es
    # el que se ve en la tienda, redimensionado por ellos.
    icono(400).save(os.path.join(AQUI, 'icon_tienda_400.png'))
    arranque().save(os.path.join(AQUI, 'splash.png'))
    print('Generados icon.png (130), largeIcon.png (130), icon_tienda_400.png '
          'y splash.png (1920x1080)')
