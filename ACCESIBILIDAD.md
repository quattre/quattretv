# Accesibilidad: lo que exige Europa y lo que hoy no cumplimos

Salio al rellenar el formulario de Samsung, que pide una **Declaracion de
Conformidad (DoC) del Acta Europea de Accesibilidad**. No es un tramite: es un
documento que firma la empresa. LG no lo pidio; Samsung si, y es obligatorio
para publicar en la UE.

**No nos vale la exencion de microempresa** (menos de 10 empleados), asi que hay
que cumplirlo de verdad.

## Que exige

A un servicio que da acceso a contenidos audiovisuales, la directiva le pide
transmitir **integros** los componentes de accesibilidad —subtitulos para
sordos, audiodescripcion— y **permitir seleccionarlos**. Ademas de una guia de
programacion accesible, que eso si lo tenemos.

## Que pasa hoy

Las emisiones **si** llevan la accesibilidad. Comprobado el 07/09/2026 con
ffprobe sobre el HLS de La 1, Antena 3, Telecinco y Teledeporte: cada canal
lleva **tres pistas de audio** —la principal, un segundo idioma y lo que muy
probablemente es la audiodescripcion— y **dos pistas de datos**, que es por
donde viaja el teletexto con los subtitulos.

El problema esta en dos sitios, los dos nuestros:

1. **La lista HLS que servimos es plana.** No declara ni una sola pista
   alternativa: no hay `#EXT-X-MEDIA` en ningun sitio. El televisor coge el
   primer audio y no sabe que existe nada mas.
2. **El reproductor del portal no tiene soporte de pistas.** Ni subtitulos ni
   seleccion de audio; no existe en el codigo.

O sea: **el contenido accesible llega hasta el CDN y ahi se pierde.**

## Lo probado el 07/09/2026 (sin tocar nada de produccion)

**Correccion de lo escrito arriba: las pistas NO se pierden en el CDN.** El
empaquetado ya las mapea todas -- `-map 0:v? -map 0:a? -map 0:d?` -- asi que los
tres audios y el teletexto viajan dentro de los segmentos. El problema esta mas
adelante.

Se probaron dos cosas en el Samsung TU32H5005:

1. **Con la lista plana de hoy**, el reproductor dice `audioTracks: 0` y
   `textTracks: 0`, aunque los segmentos lleven tres audios.
2. **Con una lista maestra en condiciones**, generada aqui en local desde el HLS
   publico y declarando las tres pistas con `#EXT-X-MEDIA` -- servida como
   ficheros estaticos desde iptv2 y borrada despues --, el televisor **sigue
   diciendo 0**.

O sea: **no basta con empaquetarlo bien**. El reproductor web de Tizen no expone
la API estandar de pistas por muy correcta que sea la lista.

Y el ffmpeg de cdn10 y cdn11 es un **8.0 compilado a mano SIN libzvbi**, asi que
tampoco puede decodificar el teletexto para sacar los subtitulos. Habria que
recompilarlo en las dos maquinas. cdn10 estaba con **carga 14,9**.

## Por donde iria el arreglo

Toca produccion, asi que con calma y canal por canal:

Hay dos caminos y ninguno es de una tarde:

**a) El reproductor nativo de Samsung (`webapis.avplay`).** Si expone las pistas
y deja elegirlas. Problema: como el objeto `tizen`, **solo existe dentro del
paquete**, y nuestro portal se sirve desde el servidor. Habria que meter la
reproduccion en el envoltorio, con lo que se pierde justo lo que hace comoda
esta arquitectura: que un arreglo llegue a todas las teles sin pasar por la
tienda. Y habria que hacerlo distinto en cada marca.

**b) Reproducir con hls.js en la propia pagina.** Ahi el cambio de pista de
audio y los subtitulos WebVTT los gestiona el JavaScript, sin depender de la API
del televisor, y vale igual para Samsung, LG y los decos. Es el camino que
mantiene una sola aplicacion. El riesgo es que se pasa de la reproduccion nativa
del televisor a una por software: hay que medir consumo y fluidez en los
aparatos mas flojos antes de cambiar nada.

Ademas, para los subtitulos:

- Recompilar ffmpeg con `--enable-libzvbi` en cdn10 y cdn11, y convertir el
  teletexto a WebVTT.
- Declarar las pistas en una lista maestra, **con otro nombre**, sin tocar el
  `index.m3u8` de hoy.
- Ojo con el coste: hoy se codifica un AAC por canal; exponer tres audios son
  tres codificaciones. Con cdn10 en carga 14,9 eso hay que medirlo antes.

Esto no es solo para Samsung: la normativa española de accesibilidad audiovisual
pide lo mismo, con app o sin ella.

## Como se hace sin romper produccion

cdn10 y cdn11 estan sirviendo a espectadores en directo ahora mismo. Las reglas,
antes de tocar nada:

1. **No se cambia lo que ya consumen los clientes.** El `index.m3u8` de cada
   canal se queda EXACTAMENTE como esta. Las pistas nuevas van en una lista
   maestra aparte, con otro nombre. Es añadir, no modificar: si la lista nueva
   sale mal, nadie se entera porque nadie la esta pidiendo todavia.
2. **Un canal, y de los de menos audiencia.** Cada canal es su propia unidad de
   systemd (`ffmpeg-hls@<canal>`) con su fichero de entorno, asi que se puede
   cambiar uno sin rozar los otros 80. Eso es una suerte y hay que aprovecharla.
3. **Con la vuelta atras preparada antes de empezar**: copia del fichero de
   entorno y el comando de restaurar escrito y probado, no improvisado.
4. **El portal no estrena la lista nueva hasta que este comprobada**, y cuando
   lo haga, primero solo en los aparatos de prueba. Un MAG de un cliente no
   puede ser el primero en encontrarse una lista distinta.
5. **A una hora tranquila**, no en horario de maxima audiencia.

Y una comprobacion previa que no cuesta nada: mirar cuanta gente hay viendo el
canal elegido antes de tocarlo.

## Estado

- 07/09/2026: detectado. El envio a Samsung se deja en borrador hasta tenerlo.
- Pendiente: implementarlo y, con eso hecho, redactar el DoC.
