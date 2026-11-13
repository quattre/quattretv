# Musica de fondo suave para las guias, hecha aqui (sin derechos de nadie):
# acordes largos de piano electrico/pad con un arpegio lento por encima.
import numpy as np, wave, sys
SR = 44100
BPM = 84
negra = 60 / BPM
compas = 4 * negra
# Cmaj9 - Am9 - Fmaj9 - G6(add9), dos vueltas
ACORDES = [[48, 55, 59, 62, 64], [45, 52, 55, 59, 60], [41, 48, 52, 55, 57], [43, 50, 52, 55, 57]] * 4
def hz(n): return 440 * 2 ** ((n - 69) / 12)
total = int(SR * compas * len(ACORDES)) + SR * 2
pista = np.zeros(total)
t_c = np.arange(int(SR * compas * 1.6)) / SR
for i, ac in enumerate(ACORDES):
    ini = int(i * compas * SR)
    env = np.minimum(1, t_c / 0.9) * np.exp(-t_c / 4.0)
    for n in ac:
        f = hz(n)
        tono = (np.sin(2 * np.pi * f * t_c) + 0.35 * np.sin(2 * np.pi * f * 2.003 * t_c)
                + 0.12 * np.sin(2 * np.pi * f * 3.01 * t_c)) * (1 + 0.15 * np.sin(2 * np.pi * 0.25 * t_c))
        trozo = tono * env * 0.06
        fin = min(total, ini + len(trozo))
        pista[ini:fin] += trozo[:fin - ini]
    # arpegio: corcheas suaves una octava arriba
    t_n = np.arange(int(SR * negra * 1.5)) / SR
    for k in range(8):
        n = ac[[1, 2, 3, 4, 3, 2, 3, 4][k]] + 12
        f = hz(n)
        nota = (np.sin(2 * np.pi * f * t_n) + 0.25 * np.sin(2 * np.pi * f * 2 * t_n)) * np.exp(-t_n / 0.45) * np.minimum(1, t_n / 0.01) * 0.035
        a = ini + int(k * negra / 2 * SR)
        fin = min(total, a + len(nota))
        pista[a:fin] += nota[:fin - a]
# eco sencillo para dar aire
for retardo, g in ((0.29, 0.35), (0.53, 0.2), (0.91, 0.1)):
    d = int(retardo * SR)
    pista[d:] += pista[:-d] * g
pista = pista / np.max(np.abs(pista)) * 0.8
salida = sys.argv[1]
with wave.open(salida, 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((pista * 32767).astype(np.int16).tobytes())
print('musica', round(total / SR, 1), 's')
