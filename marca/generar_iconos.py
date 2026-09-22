#!/usr/bin/env python3
"""
Genera los iconos y el splash de las apps a partir de los SVG del diseñador
(marca/svg/). Se escriben en lg_app/, que es de donde los toman las tres apps:
LG los usa tal cual, Samsung copia icon.png y splash.png, y Android saca sus
cinco tamaños del icono de 400 y el banner del centro del splash.

    python3 marca/generar_iconos.py

Decisiones:
- Fondo gris de marca (#383E42), opaco: Android y Samsung exigen iconos sin
  transparencia y el logotipo esta dibujado en blanco para fondo oscuro.
- En el icono de tienda el rotulo "Quattretv" viene en gris oscuro, invisible
  sobre el fondo: se pinta en blanco.
- A 80 y 130 px el rotulo no se lee: van solo con el simbolo (anillo + play).
"""
import io, os, re, sys
try:
    import cairosvg
except ImportError:
    sys.exit("Falta cairosvg:  pip install --user cairosvg")
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SVG = os.path.join(AQUI, 'svg')
LG = os.path.join(RAIZ, 'lg_app')
FONDO = (0x38, 0x3E, 0x42, 255)

LOGO = os.path.join(SVG, 'SVG', 'Quattretv_logo01.svg')
ICONO = os.path.join(SVG, 'Quattretv_icono-tienda', 'Quattretv_icono-tienda.svg')


def png(svg_texto, ancho):
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg_texto.encode(), output_width=ancho))).convert('RGBA')


def leer(ruta):
    with open(ruta, encoding='utf-8') as f:
        return f.read()


def sobre_fondo(im, tam):
    """Centra una imagen RGBA sobre un lienzo opaco del gris de marca."""
    lienzo = Image.new('RGBA', tam, FONDO)
    x = (tam[0] - im.width) // 2
    y = (tam[1] - im.height) // 2
    lienzo.paste(im, (x, y), im)
    return lienzo.convert('RGB')


def recortar(im):
    return im.crop(im.getbbox())


def solo_simbolo(im):
    """Se queda con el anillo y el play, sin el rotulo de debajo.

    El rotulo no se puede quitar por clase: la 'tv' lleva el mismo verde que el
    play. Se corta por geometria: el simbolo es el primer bloque de filas con
    dibujo; en cuanto aparece un hueco de filas vacias, lo que sigue es texto.
    """
    a = im.split()[-1]
    filas = [any(a.getpixel((x, y)) for x in range(0, a.width, 4)) for y in range(a.height)]
    ini = filas.index(True)
    fin, vacias = ini, 0
    for y in range(ini, a.height):
        if filas[y]:
            fin, vacias = y, 0
        else:
            vacias += 1
            if vacias > a.height // 40:
                break
    return recortar(im.crop((0, ini, im.width, fin + 1)))


icono_svg = leer(ICONO)
# Rotulo en blanco: la clase .st2 es el gris oscuro del texto.
icono_blanco = icono_svg.replace('.st2{fill:#383E42;}', '.st2{fill:#FFFFFF;}')
# Sin rotulo: se quitan los trazados del texto (todos los que llevan class="st2").
icono_sin_texto = re.sub(r'<path[^>]*class="st2"[^>]*/>', '', icono_svg)
icono_sin_texto = re.sub(r'<path[^>]*class="st2"[^>]*>.*?</path>', '', icono_sin_texto, flags=re.S)

# --- icono de tienda 400 (LG) y 512 (Play), con rotulo ---
for tam, nombre in [(400, 'icon_tienda_400.png'), (512, 'icon_tienda_512.png')]:
    im = png(icono_blanco, int(tam * 0.86))
    sobre_fondo(im, (tam, tam)).save(os.path.join(LG, nombre))

# --- icono 80 y largeIcon 130 (LG, Samsung): solo el simbolo ---
simbolo = solo_simbolo(png(icono_sin_texto, 1024))
for tam, nombre in [(80, 'icon.png'), (130, 'largeIcon.png')]:
    lado = int(tam * 0.74)
    s = simbolo.copy(); s.thumbnail((lado, lado), Image.LANCZOS)
    sobre_fondo(s, (tam, tam)).save(os.path.join(LG, nombre))

# --- splash 1920x1080: logotipo centrado. Android recorta el centro (960x540)
#     para el banner de 320x180, asi que el logotipo cabe de sobra.
logo = png(leer(LOGO), 640)
sobre_fondo(logo, (1920, 1080)).save(os.path.join(LG, 'splash.png'))

print('generados en lg_app/: icon.png 80, largeIcon.png 130, icon_tienda_400.png, icon_tienda_512.png, splash.png')
