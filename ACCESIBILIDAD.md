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

## Por donde iria el arreglo

Toca produccion, asi que con calma y canal por canal:

- En el empaquetado de cdn10/cdn11 (`ffmpeg-hls@`), mapear todas las pistas de
  audio y declararlas en una lista maestra con `#EXT-X-MEDIA`. El teletexto se
  puede convertir a WebVTT con ffmpeg.
- En el portal, un selector de audio y de subtitulos. Los televisores exponen
  `audioTracks` y `textTracks` cuando la lista los declara.
- Probar primero en **un solo canal** y con un aparato de pruebas.

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
