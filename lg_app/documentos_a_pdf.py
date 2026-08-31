#!/usr/bin/env python3
"""
Convierte los documentos del envio a PDF.

Los formularios de LG piden PDF o Word; en Markdown no los aceptan. Y merece la
pena que salgan legibles, porque el UX Scenario se lo lee una persona que va a
decidir si aprueba la app: si llega como un fichero de texto con simbolos raros,
empieza mal.

No usa ninguna libreria de Markdown a proposito — no hay ninguna instalada y no
hace falta. Los documentos son nuestros y solo usan seis cosas: titulos, parrafos,
listas, tablas, negrita y codigo. Un conversor de treinta lineas para eso es mas
facil de arreglar que una dependencia nueva.

    python3 lg_app/documentos_a_pdf.py fichero.md [mas.md ...]
"""
import html
import os
import re
import subprocess
import sys
import tempfile

ESTILO = """
@page { size: A4; margin: 20mm 18mm; }
body { font: 10.5pt/1.5 "DejaVu Sans", Arial, sans-serif; color: #1a1f22; }
h1 { font-size: 18pt; margin: 0 0 4pt; color: #3f6b12; }
h2 { font-size: 13pt; margin: 18pt 0 6pt; padding-bottom: 3pt;
     border-bottom: 1.5pt solid #81ba26; }
h3 { font-size: 11.5pt; margin: 13pt 0 4pt; color: #33484f; }
p, li { margin: 4pt 0; }
ul { margin: 4pt 0 4pt 14pt; padding: 0; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 9.5pt;
       background: #f1f4ef; padding: 1pt 3pt; border-radius: 2pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9.5pt; }
th, td { border: 0.5pt solid #c9d2cb; padding: 4pt 6pt; text-align: left;
         vertical-align: top; }
th { background: #eef3e9; }
hr { border: none; border-top: 0.5pt solid #d5dcd6; margin: 14pt 0; }
"""


def en_linea(t):
    """Negrita, cursiva y codigo. Se escapa antes para no romper el HTML."""
    t = html.escape(t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', t)
    return t


def a_html(md):
    salida, tabla, lista = [], [], False

    def cerrar_tabla():
        if not tabla:
            return
        salida.append('<table>')
        for n, fila in enumerate(tabla):
            celdas = [c.strip() for c in fila.strip().strip('|').split('|')]
            et = 'th' if n == 0 else 'td'
            salida.append('<tr>' + ''.join(
                '<%s>%s</%s>' % (et, en_linea(c), et) for c in celdas) + '</tr>')
        salida.append('</table>')
        tabla.clear()

    def cerrar_lista():
        nonlocal lista
        if lista:
            salida.append('</ul>')
            lista = False

    for linea in md.split('\n'):
        s = linea.rstrip()

        # Separador de tabla: |---|---|
        if re.match(r'^\|[\s:|-]+\|$', s):
            continue
        if s.startswith('|') and s.endswith('|'):
            cerrar_lista()
            tabla.append(s)
            continue
        cerrar_tabla()

        if not s.strip():
            cerrar_lista()
            continue
        if s.startswith('### '):
            cerrar_lista(); salida.append('<h3>%s</h3>' % en_linea(s[4:])); continue
        if s.startswith('## '):
            cerrar_lista(); salida.append('<h2>%s</h2>' % en_linea(s[3:])); continue
        if s.startswith('# '):
            cerrar_lista(); salida.append('<h1>%s</h1>' % en_linea(s[2:])); continue
        if re.match(r'^---+$', s):
            cerrar_lista(); salida.append('<hr>'); continue
        if re.match(r'^\s*[-*] ', s):
            if not lista:
                salida.append('<ul>'); lista = True
            salida.append('<li>%s</li>' % en_linea(re.sub(r'^\s*[-*] ', '', s)))
            continue
        if re.match(r'^\s*\d+\. ', s):
            if not lista:
                salida.append('<ul>'); lista = True
            salida.append('<li>%s</li>' % en_linea(re.sub(r'^\s*\d+\. ', '', s)))
            continue
        cerrar_lista()
        salida.append('<p>%s</p>' % en_linea(s))

    cerrar_tabla(); cerrar_lista()
    return '\n'.join(salida)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for ruta in sys.argv[1:]:
        md = open(ruta, encoding='utf-8').read()
        doc = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
               '<style>%s</style></head><body>%s</body></html>'
               % (ESTILO, a_html(md)))
        destino = os.path.splitext(ruta)[0] + '.pdf'
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False,
                                         encoding='utf-8') as t:
            t.write(doc); temporal = t.name
        subprocess.run(['weasyprint', temporal, destino], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.unlink(temporal)
        print('  %-24s -> %s (%.0f KB)'
              % (os.path.basename(ruta), os.path.basename(destino),
                 os.path.getsize(destino) / 1024))


if __name__ == '__main__':
    main()
