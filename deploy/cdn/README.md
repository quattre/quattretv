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

Ese 10,288 s **no es una caracteristica permanente de syfy**: es el tamano de un
salto que ocurrio una sola vez, el 16/08 a las 17:30, y que se quedo dentro de
ffmpeg dando vueltas.

Lo determinante es **a que pistas afecta el salto**:

- En antena3, 24h o lasexta, la vuelta a cero del reloj llega el mismo segundo
  al video **y a todas las pistas de audio a la vez**. ffmpeg mueve la
  correccion una vez, todo se desplaza junto, sigue cuadrado, y no vuelve a
  salir el aviso.
- A syfy le llego un salto que afecto **solo a una de las dos pistas**, y de un
  tamano desafortunado: 10,7 s, justo por encima de la linea de los 10 s. Al
  corregir el video descuadro el audio; al corregir el audio descuadro el video.
  Como la correccion es una sola para las dos, no hay salida.

Por eso **solo se arregla matando el proceso**: al arrancar de nuevo, ffmpeg
toma como referencia los primeros paquetes y ese estado se borra. Y por eso
vuelve a pasar: basta con que el origen de otro salto desigual de ese tamano.

El valor incluso se mueve algo mientras oscila: 10,720 s el dia 16, 10,288 s el
dia 19.

## Por que ningun aviso lo detecta

- `check_hls.sh` solo comprueba que `index.m3u8` siga actualizandose. syfy emite
  perfectamente, asi que para el script esta bien.
- Los sellos de tiempo de salida **tampoco lo delatan**: medidos en 8 segmentos
  seguidos, la separacion audio-video es de -0,040 s clavados, mas estable
  incluso que la de lasexta (que baila entre -0,059 y -0,075). Dentro de cada
  segmento no hay ni un salto.

O sea que mirando la emision no hay forma de verlo. El unico rastro es el bucle
del registro.

## Merece la pena ponerlo en todos los canales?

**Si.** No es cosa solo de syfy. Escaneados los 83 canales de los dos CDN
buscando la firma del bucle — el mismo valor apareciendo con signo + y con signo
-, descartando la vuelta a cero del reloj — sale esto:

| canal | CDN | valor | veces |
|---|---|---|---|
| **syfy** | cdn11 | 10,29 s | **2.000 en 41 segundos** |
| **squirrel** | cdn10 | 26,98 s | **733 + 297 + 354 + …** |
| **laochomed** | cdn10 | 10,48 s | 49 |
| realmadridtv | cdn10 | 16,68 / 20,28 / 20,53 s | 2-4 |
| valenciatv | cdn10 | 11,76 … 53,76 s (16 valores) | 2-5 |
| levantetv | cdn11 | 19,32 … 53,76 s (14 valores) | 2-5 |
| iberalia_caza | cdn11 | 10,03 s | 5 |
| castillalamancha | cdn11 | 48,24 s | 3 |

Los de cuenta alta son atascos de verdad; los de 2-5 son canales que flipan unas
pocas veces y se recuperan solos. En el momento del analisis solo syfy seguia
atascado (squirrel y laochomed dieron 0 avisos en dos minutos: lo suyo fueron
rachas), pero las rachas son reales y explican los casos sueltos que se ven de
vez en cuando en otros canales.

**Por que 30 y no mas:** el atasco mas grande encontrado es el de squirrel con
26,98 s, asi que 30 los cubre todos. Subir mas solo anadiria exposicion —
saltos de 40-50 s (valenciatv, levantetv, castillalamancha) pasarian crudos a la
emision en vez de absorberse — sin cubrir ningun caso real de atasco.

**Lo que no cubre:** el limite solo mueve la linea, no elimina el mecanismo. Un
salto desigual de mas de 30 s podria volver a atascar un canal. No se ha visto
ninguno, pero conviene saberlo.

Por eso el valor va **por defecto en la plantilla**, y el hueco `INOPTS` queda
para que un canal concreto pueda llevar la contraria si algun dia hace falta.

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

Con 30 segundos, el salto de 10,288 s de syfy pasa de largo y ffmpeg no lo toca.
Y la vuelta a cero del reloj, que son 95.443 s, sigue estando muy por encima, asi
que se sigue tratando como hasta ahora.

Es una opcion de entrada: va **antes** del `-i`.

### Como aplicarlo

La plantilla `ffmpeg-hls@.service` no deja meter opciones de entrada, asi que hay
que anadirle el hueco, con 30 s como valor por defecto. En el `ExecStart`:

```diff
   exec /usr/bin/ffmpeg -loglevel ${LOGLEVEL:-warning} -nostats \
+    ${INOPTS:--dts_delta_threshold 30} \
     -i ${SRC} \
```

Eso lo hace el script `poner_limite_discontinuidad.sh`, que hace copia de seguridad de la plantilla,
aborta si la linea del `-i` no es la esperada y no hace nada si ya estuviera
puesto. En cada CDN, como root:

```bash
sudo bash /tmp/poner_limite_discontinuidad.sh
sudo systemctl daemon-reload
```

**No hace falta reiniciar los 83 canales de golpe.** Cada uno coge la opcion
cuando le toque reiniciarse por lo que sea. Solo conviene reiniciar a mano el
que este atascado en ese momento:

```bash
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

## Como encontrar canales atascados

El escaneo que se uso para decidir esto esta en `buscar_bucles.sh`. Busca la
firma del bucle en el registro de cada canal: el mismo valor apareciendo con
signo + y con signo -, descartando la vuelta a cero del reloj. Se lanza en el
CDN y no necesita root ni toca nada:

```bash
bash buscar_bucles.sh
```

Una cuenta alta (decenas o cientos del mismo valor) es un canal atascado, y se
arregla reiniciandolo. Cuentas de 2 a 5 son flipeos que se recuperan solos.

## El vigilante que ya existe, y lo que le falta

No es un cron: es `check-hls.service`, un servicio de systemd que corre
`/usr/local/bin/check_hls.sh` como `www-data`, en bucle cada 300 s. Por canal
comprueba cuatro cosas y, si falla alguna, avisa por Telegram y reinicia el
canal:

1. que exista `index.m3u8`
2. que se haya actualizado hace menos de 20 s
3. discontinuidades — `ffmpeg -t 1 -v debug -i index.m3u8`, si salen mas de 10
4. que el directorio no pase de 800 MB

**Funciona.** En 3 dias reinicio iberalia_pesca, levantetv y calle13, los tres
por "SIN ACTUALIZAR", y los tres se restauraron. La regla de sudoers para
`www-data` existe — por eso el vigilante si puede reiniciar y el panel de CDNs
no, que va como `quattre`.

**Lo que no ve:** la comprobacion 3 busca las discontinuidades en la **salida**.
Cuando ffmpeg se atasca en el bucle de correcciones, la salida sigue siendo
impecable (-0,040 s clavados entre audio y video, sin huecos), asi que no la
detecta. El unico rastro esta en el registro del propio canal.

`anadir_deteccion_bucle.sh` le anade esa comprobacion, mirando el registro:

```bash
inv=$(systemctl show -p InvocationID --value "ffmpeg-hls@$canal.service")
bucle=$(journalctl _SYSTEMD_INVOCATION_ID="$inv" --since "2 min ago" \
        --no-pager | grep -c "timestamp discontinuity")
[ "$bucle" -gt 60 ] && reiniciar
```

Se acota al **arranque actual del proceso** (`InvocationID`), no solo a los
ultimos 2 minutos. Si no, la recomprobacion que hace el script 20 s despues de
reiniciar seguiria contando los avisos de *antes* del reinicio y siempre diria
"SIGUE FALLANDO DESPUES DEL REINICIO". Comprobado en cdn11: acotado asi, syfy
sigue dando 5.676 y lasexta 0.

**Umbral validado contra los 36 canales de cdn11**: 35 dan **0** y syfy da
**5.606**. Casi dos ordenes de magnitud de margen, asi que no hay falsos
positivos. Un canal sano solo saca unos pocos avisos cada 26,5 h, cuando el
reloj da la vuelta.

El script tambien hace dos cosas mas:

- **Mete a `www-data` en el grupo `systemd-journal`.** Hoy no esta en ningun
  grupo extra, asi que `journalctl` no le dejaria ver las unidades de los
  canales y la comprobacion daria 0 siempre. Hay que reiniciar `check-hls`
  despues para que coja el grupo.
- **Quita el permiso de lectura a los demas** (`chmod 750`). El script lleva
  dentro el token del bot de Telegram y estaba en `-rwxr-xr-x`: cualquiera con
  una shell en la maquina podia leerlo y escribir en el grupo. Lo lanza systemd
  como `www-data`, que es el dueno, asi que no necesita ese permiso.

Hace copia de seguridad, aborta si el script no es el esperado, no hace nada si
ya estuviera puesta y comprueba la sintaxis con `bash -n` antes de terminar.
