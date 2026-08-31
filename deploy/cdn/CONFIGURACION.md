# Configuración real de los CDN

Copia de lo que hay hoy en `cdn10` (185.25.27.53) y `cdn11` (185.25.27.54),
traída el 31/08/2026. **Es una fotografía, no la fuente de la verdad**: quien
manda es lo que hay en las máquinas. Sirve para dos cosas que hasta ahora no se
podían hacer:

- **Ver qué cambió** cuando algo se rompe. Antes, ajustar un canal era editar un
  fichero en un servidor y confiar en la memoria.
- **Rehacer una máquina** si se pierde, sin reconstruir 91 canales a mano.

## Qué hay aquí

| | |
|---|---|
| `cdn10/`, `cdn11/` | lo de cada máquina |
| `<cdn>/ffmpeg-hls@.service` | la plantilla systemd: una unidad por canal |
| `<cdn>/hls.conf` | nginx sirviendo el HLS por el puerto 1500 |
| `<cdn>/hls-ssl.conf` | el mismo HLS por HTTPS, añadido el 19/08/2026 |
| `<cdn>/canales/<nombre>` | un fichero por canal, el `EnvironmentFile` de su unidad |

Reparto actual: **51 canales en cdn10 y 32 en cdn11**, 83 en total. En el middleware hay 81 activos: la diferencia son canales configurados en el CDN que hoy no se sirven.

Las copias de seguridad que `limpiar_canal.sh` deja al lado (`*.bak*`,
`*.antes-*`) no se traen: no molestan a systemd, porque ninguna unidad las usa,
pero aquí solo interesa la configuración que está viva. En las máquinas siguen
estando, y conviene barrerlas de vez en cuando.

## Cómo es un canal

Tres variables, y el resto lo pone la plantilla:

```
SRC=udp://234.5.2.174:20000     # el multicast del que se lee
TRANSCODE=copy                  # copy, aac, noaac o h264
MAPS=                           # vacio = las pistas por defecto
```

Los comentarios van **en su propia línea a propósito**: systemd no los quita si
van detrás del valor y se los tragaría como parte de la variable.

- `TRANSCODE=copy` — no se toca nada, que es lo barato.
- `TRANSCODE=aac` — se convierte el audio, que es lo que necesitan los MAG 520 y
  la app de LG. A 31/08/2026 los 81 canales entregan AAC.
- `TRANSCODE=h264` — se recodifica el vídeo. Come mucha CPU; solo donde no queda
  otra.
- `MAPS=-map 0:v:0 -map 0:a?` — para los canales cuyo origen cuela una segunda
  pista de vídeo basura (vista en neox y hollywood).

## Para tocar un canal

No edites el fichero a pelo: `deploy/cdn/limpiar_canal.sh` cambia la variable,
reinicia el canal y **mide el desfase de audio antes y después**, deja copia de
seguridad y escribe el comando exacto para deshacerlo.

Ojo con la medida: el primer segmento tras reiniciar sale siempre en torno a
**−1,8 s** y es un espejismo del arranque. Hay que esperar un par de minutos y
volver a medir.

## Cómo se actualiza esta copia

```
deploy/cdn/traer_configuracion.sh
```

Se entra por SSH al puerto **12121** con el usuario `quattre`, sin contraseña.
