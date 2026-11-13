# Graba una guia en video: abre el portal en Chrome (el de servidor.py), pulsa
# teclas, pone rotulos y graba la pantalla (screencast). Luego ffmpeg lo une en
# un mp4 con la voz (Piper) y la musica de fondo. Ver LEEME.md.
# Uso: python3 grabar.py nombre guiones/nombre.txt   (una orden por linea)
#   portada:Titulo|Subtitulo  finportada  cap:texto con [OK] [▶]  capabajo:...  foto:segundos
#   voz:frase   tecla:codigo   espera:s   js:codigo   img:nombre  (captura suelta para el manual)
import base64, json, os, shutil, subprocess, sys, tempfile, time, urllib.request, wave, websocket
# El Python que tiene piper-tts y el modelo de voz: fuera del repositorio (pesan).
TTS_PY = os.environ.get('GUIAS_TTS_PY', os.path.expanduser('~/guias_tts/bin/python'))
VOZ = os.environ.get('GUIAS_VOZ', os.path.expanduser('~/guias_voces/es_ES-sharvard-medium.onnx'))
# La voz de mujer del modelo sharvard (CC BY 3.0: hay que citarla).
LOCUTORA = '1'


# Como se dice, no como se escribe: la voz leia "Quattre TV" a trozos y "OK"
# como "o ka".
DICCION = [('Quattre TV', 'Cuatre tevé'), ('Quattre', 'Cuatre'), ('OK', 'okey')]


SR = 22050
RETRASO = 1.2


def decir(texto):
    for escrito, dicho in DICCION:
        texto = texto.replace(escrito, dicho)
    return texto


def preparar_voces(guion, carpeta):
    """Las frases del guion con Piper, voz de mujer de sharvard (la mas
    española; Kokoro sonaba latinoamericana). Devuelve {frase: wav}."""
    voces = {}
    for i, l in enumerate(open(guion, encoding='utf-8')):
        if not l.startswith('voz:'):
            continue
        f = l.rstrip('\n')[4:]
        if f in voces:
            continue
        wav = os.path.join(carpeta, 'frase%03d.wav' % i)
        subprocess.run([TTS_PY, '-m', 'piper', '-m', VOZ, '-f', wav, '-s', LOCUTORA, '--noise-w-scale', '0.4',
                        '--noise-scale', '0.55', '--length-scale', '1.0'], input=decir(f).encode(), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        voces[f] = wav
    return voces


def hablar(texto, salida):
    """La frase ya hecha por preparar_voces. Devuelve cuanto dura."""
    shutil.copy(VOCES[texto], salida)
    with wave.open(salida) as w:
        return w.getnframes() / w.getframerate()

import threading
nombre, guion = sys.argv[1], sys.argv[2]
DIR = os.path.dirname(os.path.abspath(__file__))
sal = os.path.join(DIR, nombre); os.makedirs(sal, exist_ok=True)
for f in os.listdir(sal): os.remove(os.path.join(sal, f))
VOCES = preparar_voces(guion, sal)
chrome = subprocess.Popen(['google-chrome', '--headless=new', '--disable-gpu', '--remote-debugging-port=9334',
    '--user-data-dir=' + tempfile.mkdtemp(dir=DIR), '--window-size=1920,1080', '--hide-scrollbars',
    '--remote-allow-origins=*', '--mute-audio', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PREP = r"""
(function(){
 if (window.__cap) return;
 var st = document.createElement('style');
 st.textContent = '#preview{background:#16191b url(/static/stb/quattretv-anillo.svg) no-repeat center !important;background-size:220px !important;font-size:0 !important;color:transparent !important}' +
  '#preview *{display:none !important}' +
  '#__cap{position:fixed;z-index:999;transition:opacity .35s;left:749px;width:1079px;top:14px;padding:14px 26px;border-radius:14px;background:rgba(13,14,16,.92);color:#fff;font:500 30px/44px Poppins,Arial,sans-serif;display:none;box-sizing:border-box}' +
  '#__cap.abajo{left:120px;width:1680px;top:auto;bottom:34px}' +
  '#__cap b{display:inline-block;padding:0 14px;margin:0 4px;border-radius:8px;border:2px solid #fff;font-weight:600;line-height:38px}' +
  '#__cap b.am{background:#fdeb00;border-color:#fdeb00;color:#1d2023}#__cap b.ro{background:#e53935;border-color:#e53935}#__cap b.ve{background:#43a047;border-color:#43a047}#__cap b.az{background:#1e88e5;border-color:#1e88e5}' +
  '#__port{position:fixed;z-index:1000;top:0;left:0;width:100%;height:100%;transition:opacity .5s;background:#1d2023 url(/static/stb/fondo.jpg) no-repeat;background-size:100% 100%;display:none}' +
  '#__port img{position:absolute;left:160px;top:330px;height:90px}#__port h1{position:absolute;left:160px;top:470px;font:600 84px Poppins,Arial;color:#fff;margin:0}#__port p{position:absolute;left:160px;top:590px;font:400 38px Poppins,Arial;color:#bff102;margin:0}';
 document.head.appendChild(st);
 var c = document.createElement('div'); c.id='__cap'; document.body.appendChild(c);
 var p = document.createElement('div'); p.id='__port'; document.body.appendChild(p);
 window.__cap = function(t, abajo){
   if (!t) { c.style.opacity='0'; return; }
   c.className = abajo ? 'abajo' : '';
   c.innerHTML = t.replace(/\[([^\]]+)\]/g, function(m, k){
     var cl = {amarilla:'am', roja:'ro', verde:'ve', azul:'az'}[k] || '';
     return '<b class="'+cl+'">'+(cl ? 'tecla '+k : k)+'</b>'; });
   c.style.display='block'; c.style.opacity='1'; };
 window.__port = function(t, s){
   if (!t) { p.style.opacity='0'; setTimeout(function(){ if (p.style.opacity==='0') p.style.display='none'; }, 550); return; }
   p.innerHTML = '<img src="/static/stb/quattretv.svg"><h1>'+t+'</h1><p>'+(s||'')+'</p>'; p.style.display='block'; p.style.opacity='1'; };
})();
"""

FUNDIDO = 0.4
FPS = 25
try:
    for _ in range(150):
        try:
            tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9334/json')); break
        except Exception:
            time.sleep(.2)
    ws = websocket.create_connection([t for t in tabs if t['type'] == 'page'][0]['webSocketDebuggerUrl'])
    enviar = threading.Lock()
    respuestas, fotogramas = {}, []      # fotogramas: (hora, ruta)
    hay = threading.Condition()
    def leer():
        while True:
            try:
                r = json.loads(ws.recv())
            except Exception:
                return
            if r.get('method') == 'Page.screencastFrame':
                p = r['params']
                ruta = os.path.join(sal, 'c%06d.jpg' % len(fotogramas))
                open(ruta, 'wb').write(base64.b64decode(p['data']))
                fotogramas.append((time.time(), ruta))
                with enviar:
                    ws.send(json.dumps({'id': 10 ** 9 + len(fotogramas), 'method': 'Page.screencastFrameAck',
                                        'params': {'sessionId': p['sessionId']}}))
            elif 'id' in r:
                with hay:
                    respuestas[r['id']] = r; hay.notify_all()
    threading.Thread(target=leer, daemon=True).start()
    n = [0]
    def cdp(m, **p):
        with enviar:
            n[0] += 1; i = n[0]; ws.send(json.dumps({'id': i, 'method': m, 'params': p}))
        with hay:
            while i not in respuestas: hay.wait()
            return respuestas.pop(i).get('result')
    def js(code): return cdp('Runtime.evaluate', expression=code, returnByValue=True)
    cdp('Emulation.setDeviceMetricsOverride', width=1920, height=1080, deviceScaleFactor=1, mobile=False)
    cdp('Page.navigate', url='http://127.0.0.1:8765/stb/')
    time.sleep(8); js(PREP); time.sleep(.5)
    cdp('Page.startScreencast', format='jpeg', quality=90, maxWidth=1920, maxHeight=1080, everyNthFrame=1)
    # Tramos grabados [inicio, fin] y frases (tramo, hora de pared).
    tramos, frases, voz = [], [], None
    def grabar():
        # Tras un corte, un momento para que acaben los fundidos y llegue el
        # fotograma de ahora (si no, el tramo empezaba con el rotulo de antes).
        if not tramos or tramos[-1][1] is not None:
            if tramos: time.sleep(.5)
            tramos.append([time.time(), None])
    def cortar():
        if tramos and tramos[-1][1] is None: tramos[-1][1] = time.time()
    grabar()
    for linea in open(guion, encoding='utf-8'):
        linea = linea.rstrip('\n')
        if not linea.strip() or linea.startswith('#'): continue
        orden, _, v = linea.partition(':')
        if orden == 'voz': voz = v
        elif orden == 'espera':
            cortar(); time.sleep(float(v))
        elif orden == 'tecla':
            grabar()
            for t in ('rawKeyDown', 'keyUp'):
                cdp('Input.dispatchKeyEvent', type=t, windowsVirtualKeyCode=int(v), nativeVirtualKeyCode=int(v))
            time.sleep(.7)
        elif orden == 'js': print(js(v))
        elif orden in ('cap', 'capabajo'):
            js('__cap(%s, %s)' % (json.dumps(v), 'true' if orden == 'capabajo' else 'false'))
        elif orden == 'portada':
            t, _, s = v.partition('|'); js('__port(%s, %s)' % (json.dumps(t), json.dumps(s)))
        elif orden == 'finportada': js('__port("")')
        elif orden == 'img':
            time.sleep(.3)
            open(os.path.join(sal, 'img_' + v + '.png'), 'wb').write(
                base64.b64decode(cdp('Page.captureScreenshot', format='png')['data']))
        elif orden == 'foto':
            grabar()
            dur = float(v)
            if voz:
                wav = os.path.join(sal, 'voz%03d.wav' % len(frases))
                primera = not frases
                dur = max(dur, hablar(voz, wav) + 0.6 + (RETRASO if primera else 0))
                frases.append((len(tramos) - 1, time.time() + 0.3 + (RETRASO if primera else 0), wav))
                voz = None
            time.sleep(dur)
    time.sleep(.3); cortar()
    cdp('Page.stopScreencast')
finally:
    chrome.kill()

# El montaje: cada tramo con su primer fotograma (el que habia en pantalla al
# empezar) y los que llegaron dentro; entre tramos, fundido.
from PIL import Image
def en_pantalla(t):
    ult = fotogramas[0][1]
    for h, r in fotogramas:
        if h > t: break
        ult = r
    return ult
lista, T, inicio_tramo = [], 0.0, []
k = [0]
def poner(ruta, d):
    global T
    lista.append((ruta, d)); T += d
for i, (t0, t1) in enumerate(tramos):
    primero = en_pantalla(t0)
    if lista and lista[-1][0] != primero:
        a = Image.open(lista[-1][0]).convert('RGB'); b = Image.open(primero).convert('RGB')
        pasos = int(FUNDIDO * FPS)
        for j in range(1, pasos):
            k[0] += 1; r = os.path.join(sal, 'f%05d.jpg' % k[0])
            Image.blend(a, b, j / pasos).save(r, quality=92); poner(r, 1.0 / FPS)
    inicio_tramo.append(T)
    dentro = [(h, r) for h, r in fotogramas if t0 < h < t1]
    marcas = [(t0, primero)] + dentro
    for j, (h, r) in enumerate(marcas):
        fin = marcas[j + 1][0] if j + 1 < len(marcas) else t1
        if fin - h > 0.001: poner(r, fin - h)
with open(os.path.join(sal, 'lista.txt'), 'w') as l:
    for f, d in lista: l.write("file '%s'\nduration %.4f\n" % (f, d))
    l.write("file '%s'\n" % lista[-1][0])
mudo = os.path.join(DIR, nombre + '.mp4')
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(sal, 'lista.txt'),
    '-vf', 'fps=%d,format=yuv420p' % FPS, '-c:v', 'libx264', '-profile:v', 'high', '-level', '4.0',
    '-preset', 'slow', '-crf', '19', '-g', '50', '-movflags', '+faststart', mudo], check=True)
dur = T
pista = bytearray(int(dur * SR + SR) * 2)
for tramo, hora, wav in frases:
    t = inicio_tramo[tramo] + (hora - tramos[tramo][0])
    with wave.open(wav) as w:
        datos = w.readframes(w.getnframes())
    ini = int(t * SR) * 2
    pista[ini:ini + len(datos)] = datos[:max(0, len(pista) - ini)]
voz_total = os.path.join(sal, 'voz_total.wav')
with wave.open(voz_total, 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(pista))
con = os.path.join(DIR, nombre + '_m.mp4')
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', mudo,
    '-stream_loop', '-1', '-i', os.path.join(DIR, 'musica.wav'), '-i', voz_total,
    '-filter_complex',
    '[1:a]aresample=44100,volume=0.14,afade=t=in:d=1.5,afade=t=out:st=%.1f:d=2.5,atrim=0:%.1f[m];'
    '[2:a]aresample=44100,volume=0.7[v];[m][v]amix=inputs=2:normalize=0:duration=first,acompressor=threshold=0.1:ratio=3:attack=10:release=200:makeup=3.3,alimiter=limit=0.87:level=disabled,aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:%.1f[a]' % (dur - 2.5, dur, dur),
    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', con], check=True)
os.replace(con, mudo)
print('hecho', nombre, round(dur, 1), 's', len(fotogramas), 'fotogramas', len(tramos), 'tramos')
