# Vídeos de ayuda del portal

Los vídeos que se ven en *Menú → Ayuda* y al estrenar una novedad
(`media/ayuda/novedades.mp4`, `basico.mp4`, `guia.mp4`, `videoclub.mp4` en el servidor)
se graban solos con lo que hay aquí: se abre el portal en Chrome, se pulsan teclas según un
guion, se graba la pantalla y se le pone voz y música.

## Qué hay

| Fichero | Para qué |
|---|---|
| `servidor.py` | Sirve el portal de este repositorio en `127.0.0.1:8765` con los datos reales de iptv2 (cuenta de pruebas). No escribe nada en la cuenta. |
| `grabar.py` | Graba un vídeo a partir de un guion. |
| `guiones/*.txt` | Un guion por vídeo: una orden por línea (`portada`, `cap`, `capabajo`, `voz`, `tecla`, `foto`, `espera`, `js`). |
| `musica.py` | Hace la música de fondo (propia, sin derechos de nadie). |
| `crear_avisos.py`, `textos_sin_colores.py` | Dan de alta y ponen los textos de las guías (modelo `Aviso`); se pasan por `manage.py shell`. |

## Lo que hace falta y no está en el repositorio

- **google-chrome** y **ffmpeg** en el PC.
- Python con `websocket-client`, `Pillow` y `numpy`.
- Un entorno con **piper-tts** y la voz `es_ES-sharvard-medium.onnx` (licencia CC BY 3.0: hay que citarla).
  Por defecto se buscan en `~/guias_tts/bin/python` y `~/guias_voces/`; se cambian con `GUIAS_TTS_PY` y `GUIAS_VOZ`.
- Las **MAC de las cuentas de pruebas** (`GUIAS_MAC` y, si es otra, `GUIAS_MAC_ARCHIVO`). Son la credencial de la
  cuenta: no se escriben aquí.

## Cómo se graba uno

```
python3 musica.py musica.wav                      # una vez
GUIAS_MAC=... GUIAS_MAC_ARCHIVO=... python3 servidor.py /ruta/al/repositorio &
python3 grabar.py novedades guiones/novedades.txt # deja novedades.mp4 aquí
```

Antes de subirlo, mirarlo entero (o sacar un mosaico con ffmpeg): si el portal ha cambiado, las teclas del
guion pueden acabar en otra pantalla. Se sube a `media/ayuda/` de iptv2 guardando el anterior.

## Cómo son los rótulos

Caja oscura redondeada, **sin barra ni marca de color al lado del texto** (se quitó el 13/11/2026). Arriba a la
derecha (`cap`) o abajo a lo ancho (`capabajo`). Las teclas van entre corchetes: `[OK]`, `[▶]`, `[amarilla]`.
