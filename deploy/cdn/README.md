# syfy: por que se descompensa el audio y por que solo se arregla reiniciando

Analisis hecho el 19/08/2026 sobre cdn11, con el proceso llevando 6 dias en
marcha (arrancado el 13/08 a las 14:29).

## Lo que se ve en el registro

Desde el **16/08 a las 17:30** — tres dias despues de arrancar, no desde el
principio — ffmpeg repite sin parar este par de lineas, unas **10 veces por
segundo**:

```
[vist#0:0/h264] timestamp discontinuity (stream id=1501):  10288000, new offset= 477207932445
[aist#0:1/mp2 ] timestamp discontinuity (stream id=1502): -10288000, new offset= 477218220445
```

Video dice "he saltado +10,288 s", ffmpeg corrige. Audio dice entonces "he
saltado -10,288 s", ffmpeg corrige al reves. Y vuelta a empezar, indefinidamente.
Nunca se estabiliza.

## Por que pasa

ffmpeg lleva **una sola correccion para todo el fichero de entrada**. Cuando un
paquete llega con un tiempo que se aparta del esperado mas de lo que marca
`dts_delta_threshold` — que por defecto son **10 segundos** — lo toma por un
corte del origen y mueve esa correccion.

El origen de syfy tiene un desajuste de **10,288 s** entre la pista de video y
la de audio. Es decir: justo por encima del limite de 10. En cuanto lo cruza,
ffmpeg entra en un tira y afloja del que no sale — arregla el video y con ello
descuadra el audio, arregla el audio y descuadra el video.

Y encima el valor se mueve solo: el 16/08 era 10,720 s y el 19/08 ya era
10,288 s. Va rondando la linea de los 10 segundos, cruzandola y volviendo. Por
eso el canal aguanta unos dias bien, se estropea, y **solo se arregla matando el
proceso**: al arrancar de nuevo ffmpeg toma como referencia los primeros
paquetes y la diferencia vuelve a quedar por debajo del limite.

## Por que ningun aviso lo detecta

- `check_hls.sh` solo comprueba que `index.m3u8` siga actualizandose. syfy emite
  perfectamente, asi que para el script esta bien.
- Los sellos de tiempo de salida **tampoco lo delatan**: medidos en 8 segmentos
  seguidos, la separacion audio-video es de -0,040 s clavados, mas estable
  incluso que la de lasexta (que baila entre -0,059 y -0,075). Dentro de cada
  segmento no hay ni un salto.

O sea que mirando la emision no hay forma de verlo. El unico rastro es el bucle
del registro.

## Que NO es

Se comprobo y se descarto:

- **No es la vuelta a cero del reloj de MPEG-TS.** lasexta y paramount tambien
  sacan avisos de discontinuidad, pero con un valor de 95.443,7 s, que son
  exactamente las 26,5 horas del contador de 33 bits (2^33 / 90000). Eso es
  normal y no molesta a nadie. Lo de syfy, 10,288 s, no es eso.
- **No es deriva del reloj de audio.** Si lo fuera, la separacion entre audio y
  video iria creciendo segmento a segmento. Es constante.
- **No es perdida de paquetes** ni saltos dentro de los segmentos: no hay
  huecos ni en el audio ni en el video.

## El arreglo

Subir el limite por encima de ese desajuste, para que ffmpeg deje de "corregir"
algo que no es un corte de verdad:

    -dts_delta_threshold 30

Con 30 segundos, el desajuste de 10,288 s de syfy pasa de largo y ffmpeg no lo
toca. Y la vuelta a cero del reloj, que son 95.443 s, sigue estando muy por
encima, asi que se sigue tratando como hasta ahora. Los demas canales no se
enteran del cambio.

Es una opcion de entrada: va **antes** del `-i`.

### Como aplicarlo

La plantilla `ffmpeg-hls@.service` no deja meter opciones de entrada, asi que hay
que anadirle un hueco. En el `ExecStart`:

```diff
   exec /usr/bin/ffmpeg -loglevel ${LOGLEVEL:-warning} -nostats \
+    ${INOPTS:-} \
     -i ${SRC} \
```

Y luego, solo en el canal que lo necesita, en `/home/quattre/canales/syfy`:

```
# El origen trae video y audio separados 10,288 s, justo por encima del limite
# de 10 s que trae ffmpeg de fabrica, y eso lo mete en un bucle de correcciones
# del que no sale hasta que se reinicia. Con 30 lo deja pasar.
# El comentario va en su propia linea: systemd NO lo quita si va detras del valor.
INOPTS=-dts_delta_threshold 30
```

Ambas cosas necesitan root en cdn11:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ffmpeg-hls@syfy
```

### Como comprobar que ha funcionado

El bucle tiene que desaparecer del registro:

```bash
journalctl -u ffmpeg-hls@syfy -f | grep discontinuity
```

Antes salian ~10 lineas por segundo. Despues no deberia salir ninguna con el
valor 10288000. Las de 95443717689 (la vuelta a cero, cada 26,5 h) si pueden
seguir saliendo y son normales.

La prueba de verdad es el tiempo: si aguanta una semana sin que haya que matar
el proceso, era esto.

## Si aun asi se sigue descompensando

Entonces el desfase viene ya en el origen y no lo mete ffmpeg. En ese caso se
corrige desplazando el audio a mano en la entrada:

    -itsoffset 0.4 -i ${SRC}      # aplicado solo a la pista de audio

pero eso hay que ajustarlo mirando la tele, porque no hay forma de medirlo desde
el servidor.
