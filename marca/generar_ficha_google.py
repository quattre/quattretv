#!/usr/bin/env python3
"""
Prepara el material grafico que pide la ficha de Google Play para una
aplicacion de Android TV, a partir de los SVG del diseñador (marca/svg/).

    python3 marca/generar_ficha_google.py

Lo que exige Google Play, y por que cada medida:
  - Icono 512x512 PNG. El de la tienda, con rotulo.
  - Grafico destacado 1024x500. Sale en la cabecera de la ficha. Sin
    transparencia, y el logotipo no puede tocar los bordes porque Google lo
    recorta en algunos sitios.
  - Banner de TV 1280x720. **Obligatorio** para Android TV: es lo que se ve en
    la fila de aplicaciones del televisor.
Todo sobre el gris de marca opaco: Play rechaza los graficos con alfa.
"""
import io, os, sys
try:
    import cairosvg
except ImportError:
    sys.exit("Falta cairosvg:  pip install --user cairosvg")
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(AQUI, 'svg')
SALIDA = os.path.expanduser('~/envio-google/ficha')
FONDO = (0x38, 0x3E, 0x42)

LOGO = os.path.join(SVG, 'SVG', 'Quattretv_logo01.svg')
ICONO = os.path.join(SVG, 'Quattretv_icono-tienda', 'Quattretv_icono-tienda.svg')


def png(ruta, ancho, reemplazos=()):
    with open(ruta, encoding='utf-8') as f:
        texto = f.read()
    for a, b in reemplazos:
        texto = texto.replace(a, b)
    return Image.open(io.BytesIO(
        cairosvg.svg2png(bytestring=texto.encode(), output_width=ancho))).convert('RGBA')


def sobre_fondo(im, tam, proporcion):
    """Centra el dibujo ocupando 'proporcion' del ancho, sobre fondo opaco."""
    lienzo = Image.new('RGB', tam, FONDO)
    ancho = int(tam[0] * proporcion)
    copia = im.copy()
    copia.thumbnail((ancho, int(tam[1] * proporcion)), Image.LANCZOS)
    lienzo.paste(copia, ((tam[0] - copia.width) // 2, (tam[1] - copia.height) // 2), copia)
    return lienzo


os.makedirs(SALIDA, exist_ok=True)
# El rotulo del icono viene en gris oscuro, invisible sobre el fondo de marca.
blanco = (('.st2{fill:#383E42;}', '.st2{fill:#FFFFFF;}'),)

icono = png(ICONO, 460, blanco)
sobre_fondo(icono, (512, 512), 0.88).save(os.path.join(SALIDA, 'icono_512.png'))

logo = png(LOGO, 1400)
# El destacado y el banner llevan el logotipo horizontal, holgado: Google
# recorta los bordes del destacado en la ficha movil.
sobre_fondo(logo, (1024, 500), 0.62).save(os.path.join(SALIDA, 'destacado_1024x500.png'))
sobre_fondo(logo, (1280, 720), 0.58).save(os.path.join(SALIDA, 'banner_tv_1280x720.png'))

for n in ('icono_512.png', 'destacado_1024x500.png', 'banner_tv_1280x720.png'):
    im = Image.open(os.path.join(SALIDA, n))
    print(f'  {n:28s} {im.size[0]}x{im.size[1]} {im.mode}')
print(f'en {SALIDA}')
