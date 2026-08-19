# Canales que pierden la sincronia del audio

Algunos canales van desincronizando el sonido con las horas: el reloj de audio
del emisor y el de video no van exactamente iguales, el audio se desliza y a los
pocos dias ya se nota. Los sellos de tiempo siguen siendo correctos, asi que
`check_hls.sh` no puede detectarlo — solo comprueba que el canal emita.

## Solucion inmediata: reinicio nocturno

Es lo mismo que se hacia a mano, pero sin acordarse:

```bash
sudo cp ffmpeg-hls-reinicio@.service ffmpeg-hls-reinicio@.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ffmpeg-hls-reinicio@syfy.timer

systemctl list-timers 'ffmpeg-hls-reinicio@*'   # comprobar
```

A las 5:00 con un margen aleatorio de 5 minutos, para no reiniciar todos los
canales a la vez si se aplica a varios. El corte dura los pocos segundos que
tarda ffmpeg en reenganchar el multicast.

Para aplicarlo a otro canal basta con habilitar su temporizador:
`sudo systemctl enable --now ffmpeg-hls-reinicio@<canal>.timer`

## Solucion de fondo: corregir la deriva en vez de reiniciar

El reinicio es un parche. La forma de atacarlo de raiz es recodificar el audio
dejando que ffmpeg lo reajuste a la linea de tiempo, que es justo lo que corrige
esa deriva:

    -c:a aac -b:a 128k -ac 2 -af aresample=async=1000

`aresample=async` estira o recorta el audio unas milesimas segun hace falta para
mantenerlo pegado al video, en vez de dejar que la diferencia se acumule.

Requiere anadir un modo nuevo a la plantilla `ffmpeg-hls@.service` (por ejemplo
`TRANSCODE=aacsync`) y cuesta CPU, porque ya no es copia directa: en las
mediciones, reempaquetar sale casi gratis pero recodificar audio a AAC ronda el
2 % de un nucleo por canal. Para un canal suelto es asumible.

Conviene probarlo en syfy antes de generalizarlo: la conversion a AAC a secas ya
se probo en su dia y metia un desfase fijo de 2,7 s. Lo que lo arregla es el
`aresample=async`, no el AAC.
