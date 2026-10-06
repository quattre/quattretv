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

## Que pasa hoy — MEDIDO EL 06/10/2026, y dos cosas que teniamos mal

**Lo que lleva la fuente** (multicast de La 1, `udp://234.5.2.174:20000`,
leido con ffprobe desde cdn10):

| Flujo | Que es |
|---|---|
| h264 | video |
| eac3 `spa` | audio principal |
| eac3 `qaa` | version original |
| eac3 `spa` **(visual impaired) (descriptions)** | **audiodescripcion, etiquetada en origen** |
| dvb_subtitle `spa` | subtitulos en imagen |
| **dvb_teletext `spa`** | **teletexto — aqui van los subtitulos para sordos, pagina 888** |
| dvb_subtitle `qaa`, scte_35, epg | lo demas |

**ERROR 1 QUE TENIAMOS APUNTADO: los subtitulos no se pierden "mas adelante",
es que NO LOS COPIAMOS.** La plantilla de systemd mapea
`-map 0:v? -map 0:a? -map 0:d?` — video, audio y **datos**. No hay `-map 0:s?`,
asi que los tres flujos de subtitulos se quedan fuera en nuestro ffmpeg. Lo que
llegaba al HLS como `bin_data` era el SCTE-35 y la EPG, no los subtitulos.

**ERROR 2: el ffmpeg de los CDN es el 6.1.1 de la distribucion, no un 8.0
compilado a mano, y SI lleva `libzvbi`.** No hay que recompilar nada.

**Y una tercera cosa, esta a favor:** los tres audios **ya se recodifican a AAC
hoy** (`-c:a aac -b:a 128k -ac 2` se aplica a todos los mapeados). Exponerlos no
cuesta ni un ciclo mas de CPU.

## Probado entero el 06/10/2026, sin tocar produccion

Con una muestra de 30 s del multicast traida a local, **una sola orden de ffmpeg**
produce lo que exige la norma:

```
ffmpeg -txt_format text -txt_page 888 -fix_sub_duration -i <fuente> \
  -map 0:v:0 -map 0:a:0 -map 0:a:1 -map 0:a:2 -c:v copy -c:a aac -b:a 128k -ac 2 \
  -f hls -hls_time 10 -hls_segment_type mpegts -master_pl_name master.m3u8 \
  -var_stream_map "v:0,agroup:aud a:0,agroup:aud,language:spa \
                   a:1,agroup:aud,language:qaa a:2,agroup:aud,language:spa" \
  -hls_segment_filename "s%v_%03d.ts" "s%v.m3u8" \
  -map 0:s:1 -c:s webvtt \
  -f segment -segment_time 10 -segment_format webvtt \
  -segment_list subtitulos.m3u8 -segment_list_type m3u8 "sub_%03d.vtt"
```

Tres detalles que costaron encontrarlos:
- **`-txt_page 888`**. Sin eso, el teletexto vuelca TODAS las paginas: el indice,
  el tiempo, la loteria. La 888 es la de subtitulos en España, y sale limpia y
  con los tiempos bien. El primer subtitulo de la muestra es `(MUSICA)`, que es
  la marca de los subtitulos para sordos.
- **El muxer de HLS no sabe escribir una salida solo de subtitulos**, y mezclar
  `agroup` con `sgroup` en `-var_stream_map` da *"No streams to mux"*. Se saca
  con el muxer **segment**, en la misma orden: una decodificacion, dos salidas.
- **La lista maestra se escribe a mano.** ffmpeg no junta las dos salidas, y
  ademas pone `DEFAULT=YES` en los tres audios. Escribiendola nosotros se
  controlan los idiomas, cual manda y —lo importante— las marcas de
  accesibilidad: `CHARACTERISTICS="public.accessibility.describes-video"` en la
  audiodescripcion y `describes-music-and-sound` en los subtitulos.

**Comprobado en ExoPlayer** (muestra servida por HTTPS desde iptv2): ve los tres
audios y los subtitulos, con `roles=512` en la audiodescripcion y `roles=1024`
en los subtitulos. O sea que el reproductor no solo las lista: **sabe para que
sirve cada una**, que es justo lo que pide el Anexo I.

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
