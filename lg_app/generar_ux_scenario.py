#!/usr/bin/env python3
"""
Genera el UX Scenario en el formato que pide LG.

LG entrega una plantilla en PowerPoint (ux_scenario_document_4.4.ppt) y lo que
espera no es un texto: es un documento visual. Cada pantalla con su captura, un
numero encima de cada elemento de la interfaz, y una tabla al lado explicando
que hace cada numero. Su propia guia lo dice: "Use unique number to indicate
each menu or UI button correctly".

Aqui se construye ese mismo documento en PDF —que el formulario acepta— con las
capturas reales del televisor, anotadas. Se hace en PDF y no en su PowerPoint
porque no hay con que editar un .ppt en esta maquina, y porque asi el documento
se rehace de un tiron cada vez que cambia la interfaz, en vez de tener que
arrastrar imagenes a mano.

    python3 lg_app/generar_ux_scenario.py <carpeta-de-capturas> <destino.pdf>
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

VERDE = (129, 186, 38)
ROJO = (214, 45, 45)

# Para cada pantalla: fichero, titulo, y los numeros con su posicion y su
# explicacion. Las posiciones son en pixeles sobre la captura de 1920x1080.
PANTALLAS = [
    {
        'fichero': '00-acceso.png',
        'seccion': '4. Detailed Login Information',
        'titulo': 'Sign-in screen',
        'intro': 'Shown the first time the app runs on a television, or after the '
                 'customer\'s device has been removed from their account. On every '
                 'later start the app goes straight to the channel list.',
        'puntos': [
            (960, 458, 'User name field. Focus opens the webOS on-screen keyboard. '
                       'Move between fields with the up and down keys.'),
            (960, 525, 'Password field, masked. Same keyboard behaviour.'),
            (960, 596, 'Sign-in button. OK on the remote signs in. If the credentials '
                       'are wrong, or the subscription is inactive, or the device limit '
                       'is reached, the reason is shown on this same screen.'),
        ],
    },
    {
        'fichero': '01-canales.png',
        'seccion': '5. Main Page Description',
        'titulo': 'Channel list — the main screen',
        'intro': 'The app opens here. The channel under the cursor plays in the '
                 'preview window on the right.',
        'puntos': [
            (300, 300, 'Channel list: number, name and the programme currently on air, '
                       'with a progress bar. Up and down move through it.'),
            (300, 722, 'Selected channel. OK plays it full screen.'),
            (1310, 435, 'Preview of the selected channel, playing live.'),
            (1000, 880, 'What is on now and what is on next, for the selected channel.'),
            (330, 975, 'On-screen key legend: OK to watch, RIGHT for the guide, LEFT for '
                       'the menu, and the number keys to jump to a channel.'),
        ],
    },
    {
        'fichero': '02-menu.png',
        'seccion': '6. Sub Page Description',
        'titulo': 'Main menu',
        'intro': 'Opened with the LEFT key or BACK from the channel list. The menu is '
                 'built from what the subscription includes: with the review account it '
                 'shows three options. Accounts with films, series or recordings see '
                 'those as well. An option that does not apply is never shown.',
        'puntos': [
            (330, 200, 'Menu options. Up and down to move, OK to enter.'),
            (330, 990, 'Key legend: OK to enter, LEFT to go back to the channel list.'),
            (1310, 435, 'The channel keeps playing while the menu is open.'),
        ],
    },
    {
        'fichero': '03-categorias.png',
        'seccion': '6. Sub Page Description',
        'titulo': 'Categories',
        'intro': 'Filters the channel list by genre. Selecting a category returns to '
                 'the channel list showing only those channels.',
        'puntos': [
            (700, 200, 'Category list. The active one is marked.'),
            (700, 990, 'Key legend: OK to choose, LEFT to go back.'),
        ],
    },
    {
        'fichero': '04-guia.png',
        'seccion': '6. Sub Page Description',
        'titulo': 'Programme guide',
        'intro': 'Opened with the RIGHT key from the channel list. Shows the whole day '
                 'for the selected channel.',
        'puntos': [
            (330, 250, 'Programmes of the day, with their start time.'),
            (560, 468, 'Selected programme. The one on air is marked. The arrow on the '
                       'right means this row can be opened for full details.'),
            (330, 858, 'Beginning of the synopsis.'),
            (250, 956, 'Press RIGHT again to open the full programme details.'),
        ],
    },
    {
        'fichero': '05-ficha.png',
        'seccion': '6. Sub Page Description',
        'titulo': 'Programme details',
        'intro': 'Opened with the RIGHT key from the guide, or with the INFO key from '
                 'anywhere. RIGHT always means "go one level deeper": channel list, '
                 'guide, details.',
        'puntos': [
            (330, 180, 'Programme title, with a badge when it is the one on air.'),
            (200, 213, 'Start and end time, duration and category.'),
            (330, 290, 'Full synopsis. If it does not fit, up and down scroll it and a '
                       'marker shows there is more below.'),
            (370, 735, 'Key legend: LEFT goes back to the guide.'),
        ],
    },
    {
        'fichero': '06-completa.png',
        'seccion': '6. Sub Page Description',
        'titulo': 'Full-screen playback',
        'intro': 'Reached with OK from the channel list. Up and down change channel; '
                 'OK or BACK return to the list.',
        'puntos': [
            (960, 300, 'The channel, full screen.'),
            (430, 890, 'Channel banner: number, name, what is on now with its progress, '
                       'and what is on next. It appears when the channel changes and '
                       'hides itself after a few seconds.'),
            (1690, 1006, 'What can be done from here: RIGHT opens the programme details '
                         'without leaving the video.'),
        ],
    },
]


def anotar(origen, destino, puntos):
    """Pone los numeros sobre la captura, como pide la guia de LG."""
    im = Image.open(origen).convert('RGB')
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 40)
    except Exception:
        f = ImageFont.load_default()
    r = 33
    for n, (x, y, _) in enumerate(puntos, 1):
        # Aro blanco por fuera: sobre una imagen oscura o clara, siempre se ve
        d.ellipse([x - r - 4, y - r - 4, x + r + 4, y + r + 4], fill=(255, 255, 255))
        d.ellipse([x - r, y - r, x + r, y + r], fill=ROJO)
        t = str(n)
        caja = d.textbbox((0, 0), t, font=f)
        d.text((x - (caja[2] - caja[0]) / 2, y - (caja[3] - caja[1]) / 2 - caja[1]),
               t, font=f, fill=(255, 255, 255))
    im.save(destino)


ESTILO = """
@page { size: A4 landscape; margin: 12mm 12mm 10mm; }
body { font: 9.5pt/1.45 "DejaVu Sans", Arial, sans-serif; color: #1a1f22; margin: 0; }
.portada { text-align: center; padding-top: 42mm; }
.portada h1 { font-size: 30pt; color: #3f6b12; margin: 0 0 4mm; }
.portada .sub { font-size: 12pt; color: #55636a; margin-bottom: 18mm; }
.seccion { page-break-before: always; }
h2 { font-size: 14pt; margin: 0 0 1mm; color: #3f6b12; }
h3 { font-size: 11pt; margin: 0 0 2mm; color: #33484f; font-weight: 600; }
.intro { font-size: 9pt; color: #45535a; margin: 0 0 3mm; max-width: 250mm; }
/* Tabla y no flex: weasyprint no respeta el ancho de una imagen dentro de un
   contenedor flex y la captura salia diminuta, que es justo lo que no puede
   pasar en un documento cuyo objeto es que se vea la interfaz. */
table.fila { border-collapse: separate; border-spacing: 0; width: 100%; }
table.fila td { border: none; padding: 0; vertical-align: top; }
td.captura { width: 176mm; padding-right: 5mm !important; }
td.captura img { width: 176mm; border: 0.4pt solid #c9d2cb; display: block; }
table { border-collapse: collapse; font-size: 8.5pt; width: 100%; }
th, td { border: 0.4pt solid #c9d2cb; padding: 1.6mm 2mm; text-align: left;
         vertical-align: top; }
th { background: #eef3e9; }
td.n { width: 8mm; text-align: center; font-weight: 700; color: #b52a2a; }
table.datos { max-width: 190mm; }
table.datos td:first-child { width: 55mm; background: #f6f8f4; font-weight: 600; }
.nota { font-size: 8.5pt; color: #55636a; margin-top: 3mm; max-width: 250mm; }
.aviso { border-left: 3pt solid #81ba26; padding: 2mm 0 2mm 4mm; margin-top: 4mm;
         background: #f7faf4; }
"""


def tabla_puntos(puntos):
    filas = ''.join(
        '<tr><td class="n">%d</td><td>%s</td></tr>' % (n, texto)
        for n, (_, _, texto) in enumerate(puntos, 1))
    return ('<table><tr><th colspan="2">Description</th></tr>%s</table>' % filas)


def construir(carpeta, destino):
    tmp = tempfile.mkdtemp()
    partes = ["""
<div class="portada">
  <h1>QuattreTV</h1>
  <div class="sub">UX Scenario Document</div>
  <table class="datos" style="margin:0 auto; max-width:120mm;">
    <tr><td>Submission Date</td><td>2026 / 08 / 26</td></tr>
    <tr><td>App Ver.</td><td>1.1.0</td></tr>
    <tr><td>App ID</td><td>com.quattre.tv</td></tr>
    <tr><td>App Developer</td><td>Quattre Internet S.L.<br>info@quattre.com</td></tr>
  </table>
</div>

<div class="seccion">
<h2>1. Basic Information</h2>
<table class="datos">
  <tr><td>App Title</td><td>QuattreTV</td></tr>
  <tr><td>Category</td><td>Entertainment</td></tr>
  <tr><td>File Type</td><td>Web</td></tr>
  <tr><td>Optimized Resolution</td><td>1920 x 1080</td></tr>
  <tr><td>Service Area Information</td><td>Spain</td></tr>
  <tr><td>App Service Language</td><td>Spanish</td></tr>
  <tr><td>Geo-IP Block</td><td>No</td></tr>
  <tr><td>SDK Version</td><td>webOS 1.1.0 &mdash; 2014 and all later platforms</td></tr>
  <tr><td>In-App Ad</td><td>Not Applicable</td></tr>
  <tr><td>Paid Content</td><td>Subscription &mdash; arranged outside the app, at
      quattre.com or in the operator's shops. Nothing can be purchased from the
      television.</td></tr>
  <tr><td>Service URL</td><td>https://iptv2.quattre.com/quattretv/stb/</td></tr>
  <tr><td>Service Platform</td><td>webOS</td></tr>
</table>
<div class="aviso">
<strong>The service is subscription-only.</strong> Every screen beyond sign-in
requires valid customer credentials. A test account is given in section 4.
There is no user-generated content, no advertising and no link out of the app.
</div>
</div>

<div class="seccion">
<h2>2. Document History</h2>
<table class="datos" style="max-width:170mm;">
  <tr><th>No.</th><th>Sent</th><th>Version</th><th>File Name</th><th>Contents</th></tr>
  <tr><td>1</td><td>26.08.2026</td><td>1.1.0</td><td>UX Scenario</td>
      <td>Initial document</td></tr>
</table>
</div>
"""]

    for p in PANTALLAS:
        origen = os.path.join(carpeta, p['fichero'])
        if not os.path.exists(origen):
            print('  falta %s, se salta' % p['fichero'])
            continue
        img = os.path.join(tmp, 'a_' + p['fichero'])
        anotar(origen, img, p['puntos'])
        partes.append("""
<div class="seccion">
  <h2>%s</h2>
  <h3>%s</h3>
  <p class="intro">%s</p>
  <table class="fila"><tr>
    <td class="captura"><img src="file://%s"></td>
    <td>%s</td>
  </tr></table>
</div>""" % (p['seccion'], p['titulo'], p['intro'], img, tabla_puntos(p['puntos'])))

    partes.append("""
<div class="seccion">
<h2>4. Test account and parental control</h2>
<table class="datos">
  <tr><td>User</td><td>lgreview</td></tr>
  <tr><td>Password</td><td>QuattreLG2026</td></tr>
  <tr><td>Expiry</td><td>None. The account does not expire.</td></tr>
  <tr><td>Devices</td><td>5, with 2 concurrent streams</td></tr>
  <tr><td>Parental PIN</td><td>1234</td></tr>
  <tr><td>Adult channel to test it with</td><td>Channel 29, &ldquo;Dark&rdquo;</td></tr>
  <tr><td>Subscription</td><td>Live TV: 81 channels and the programme guide. Films,
      series and recordings are <strong>not</strong> enabled on this account, so
      those menu options do not appear.</td></tr>
</table>

<h3 style="margin-top:5mm">Authentication method for adult content: PIN code (parental lock)</h3>
<p class="intro">The service carries adult channels and they are declared here on
purpose. This is how the lock works, and it is worth checking:</p>
<table class="datos" style="max-width:250mm">
  <tr><td>In the channel list</td><td>Channel 29 shows a padlock. The preview window
      does not play it and says the channel is locked.</td></tr>
  <tr><td>Pressing OK on it</td><td>The PIN screen opens. Digits are entered with the
      number keys or by pointing at the on-screen keypad with the Magic Remote.
      A wrong PIN is rejected and rate-limited.</td></tr>
  <tr><td>With the correct PIN</td><td>The device is unlocked for 30 minutes and
      then locks itself again.</td></tr>
  <tr><td>Underneath</td><td><strong>While the channel is locked, the server sends
      the channel entry with an empty address.</strong> There is no stream URL on
      the television to be found. The lock does not depend on the application and
      cannot be bypassed from it.</td></tr>
  <tr><td>Channel 30, &ldquo;Dark Sin X&rdquo;</td><td>The same channel without the
      adult content. It is not locked, which shows the lock applies per channel.</td></tr>
</table>
</div>

<div class="seccion">
<h2>7. Paid Content</h2>
<p class="intro">The application is free and <strong>nothing can be purchased inside
it</strong>. There is no payment screen, no account upgrade and no link to one.</p>
<p class="intro">The television service itself is a subscription, arranged and paid
for outside the application &mdash; at quattre.com or in the operator's shops.
Following LG's guidance, the app is therefore declared as <strong>Subscription</strong>
with third-party billing, even though no payment process exists within the app.</p>

<h2 style="margin-top:8mm">8. In-App Ad</h2>
<p class="intro">Not applicable. The application contains no advertising of any
kind, no banner ads and no AVOD.</p>

<h2 style="margin-top:8mm">Remote control and behaviour when the network fails</h2>
<table class="datos" style="max-width:250mm">
  <tr><td>Remote</td><td>Works with both the Magic Remote and a standard remote. Every
      screen is operable with the 4-way pad, OK and BACK; no pointer is required.
      With the Magic Remote, rows respond to the pointer &mdash; the first click
      selects and the second enters &mdash; and the wheel scrolls long lists.</td></tr>
  <tr><td>BACK key</td><td>Handled by the app (<code>disableBackHistoryAPI</code> is
      true). BACK always leads back towards the channel list; from the channel list
      it opens the main menu. No screen can be got stuck in.</td></tr>
  <tr><td>Colour buttons</td><td>Red records, green marks a favourite, yellow filters
      favourites, blue opens the guide. INFO opens the programme details.</td></tr>
  <tr><td>No network at start</td><td>The app asks the service before loading anything.
      If nothing answers it shows a plain message and a retry button that holds the
      focus &mdash; never a blank screen. It also retries by itself, and reconnects
      the moment the television reports the network is back.</td></tr>
  <tr><td>Network lost while watching</td><td>A message appears over the video with a
      countdown to the next attempt. When the network returns, the channel list is
      reloaded and the channel resumes on its own.</td></tr>
</table>
</div>
""")

    html = ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>%s</style>'
            '</head><body>%s</body></html>' % (ESTILO, ''.join(partes)))
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False,
                                     encoding='utf-8') as t:
        t.write(html)
        ruta = t.name
    subprocess.run(['weasyprint', ruta, destino], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.unlink(ruta)
    print('  generado: %s (%.0f KB)' % (destino, os.path.getsize(destino) / 1024))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    construir(sys.argv[1], sys.argv[2])
