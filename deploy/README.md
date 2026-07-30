# Puesta en marcha de EPG y grabaciones

## 0. Comprobar que el .env de producción está bien

`manage.py check` avisa al desplegar si `DEBUG` está activado, si
`ALLOWED_HOSTS` acepta cualquier dominio o si la `SECRET_KEY` es la de ejemplo.
Los tres hay que corregirlos en el `.env` del servidor: con `DEBUG=True`
cualquier error muestra la traza completa con la configuración.

Para vigilar el servicio en marcha hay un **`/health`**: responde 503 si la base
de datos falla, si el EPG lleva más de 6 h sin actualizarse (señal de que Celery
está parado) o si un grabador lleva más de 15 min sin pedir sus tareas.

### Mando a distancia en el portal de TV

| Tecla | Hace |
|---|---|
| OK | Ver a pantalla completa |
| ▲ ▼ | Moverse por la lista / cambiar de canal |
| ▶ | Guía del canal |
| ◀ | Categorías |
| REC o ROJO | Grabar |
| VERDE | Mis grabaciones |
| AMARILLO | Ver solo favoritos |
| AZUL | Marcar/desmarcar favorito |
| 0-9 | Ir directo a un número de canal |


Nada de esto reinventa el grabador: seguimos usando `dumpstream` de Ministra en
record1 y storage1. Lo único que cambia es quién les dice qué grabar.

## 0.5 Panel de CDNs

En **Portal → CDNs** se dan de alta los servidores de emisión (cdn10, cdn11) y
se ve, canal a canal, si están emitiendo. La comprobación **no necesita acceso
a la máquina**: se mira la playlist HLS que el CDN ya publica, y si lleva más
de un minuto sin cambiar es que ffmpeg no está escribiendo.

Con *Detectar canales* se asignan de golpe los canales cuya URL apunta a ese
CDN, sin emparejarlos a mano.

Para poder **reiniciar** un canal desde el panel hacen falta dos cosas en el
CDN: que el usuario de Django pueda entrar por SSH con clave, y esta regla de
sudoers (igual que la que ya existe para `quattretv.service`):

```
# /etc/sudoers.d/quattre-cdn
quattre ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart ffmpeg-hls@*
```

Sin eso el panel sigue funcionando, pero solo para mirar.

## 1. Celery (obligatorio)

Sin worker ni beat no se descarga el EPG ni se envía ninguna grabación: hoy en
producción solo corre `quattretv.service` (gunicorn).

```bash
sudo cp deploy/quattretv-celery.service deploy/quattretv-celery-beat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quattretv-celery quattretv-celery-beat
```

Requiere Redis escuchando en `CELERY_BROKER_URL` (por defecto
`redis://localhost:6379/1`). Las tareas periódicas se declaran en
`CELERY_BEAT_SCHEDULE` y el `DatabaseScheduler` las crea solas al arrancar:

| Tarea | Cada |
|---|---|
| `epg.update_all_epg_sources` | 1 h |
| `epg.cleanup_old_programs` | diaria (04:30) |
| `pvr.dispatch_due_recordings` | 1 min |
| `pvr.apply_recording_rules` | 1 h |
| `pvr.reconcile_recordings` | 5 min |

## 2. EPG

1. Portal → EPG → **Nueva Fuente EPG** con la URL del XMLTV.
2. Cada canal necesita su **EPG Channel ID** (el `tvg-id` del XMLTV). La
   importación M3U ya lo rellena; a mano se edita en la ficha del canal. La
   página de EPG muestra cuántos canales quedan sin mapear.
3. Botón *Actualizar ahora* para no esperar a la hora.

## 3. Grabadores (record1 / storage1)

En el admin de Django → **Storage Servers**, dar de alta cada servidor:

| Campo | Qué poner |
|---|---|
| `name` | el `STORAGE_NAME` del `config.php` del servidor |
| `role` | `archive` para storage1, `records` para record1 |
| `api_url` | base REST, ej. `http://storage1.quattre.com/storage/` |
| `playback_url` | base pública si difiere (get.php y los .mpg) |
| `token` | token compartido; se manda como `Bearer` y se valida solo |

En el `config.php` de cada storage hay que apuntar:

```php
define('API_URL',    'http://iptv1.quattre.com:8000/storage_api/');
define('PORTAL_URL', 'http://iptv1.quattre.com:8000');
```

Con eso:

- `tvarchivesync.php` pedirá su lista a
  `GET /storage_api/tv_archive/<STORAGE_NAME>` y recibirá `{"results": [...]}`
  con `ch_id`, `cmd` y `parts_number`, igual que antes.
- `dumpstream` avisará del estado de cada grabación en
  `/storage_api/stream_recorder/<rec_id>`.
- Los `chk_storage_token.php` / `chk_tmp_archive_link.php` que el storage
  consulta se sirven en `/server/api/`.

## 4. Canales

Para que un canal se archive o se pueda grabar necesita **origen multicast**
(`udp://…`) en su ficha: es el mismo `SRC` del EnvironmentFile del CDN. Los
grabadores leen del multicast, no del HLS. Sin ese dato el canal no se anuncia
con archivo a los decos y sus grabaciones fallan con un mensaje claro.

`parts_number` (horas de archivo que guarda storage1) sale de
`timeshift_hours` del canal.

## 5. Migrar el archivo de MPEG-TS a HLS sin cortar servicio

El archivo se graba hoy como MPEG-TS crudo, que el deco reproduce pero la TV LG
no. La migración se hace **canal a canal**, sin parar nada y sin perder lo ya
grabado, porque los dos formatos conviven: cada canal guarda en
`archive_hls_since` el momento del cambio, y el catchup anterior a esa fecha se
sigue sirviendo del archivo viejo hasta que caduca solo.

### En el servidor de archivo

Todo lo que hay que copiar está en `deploy/storage/`:

```bash
sudo cp deploy/storage/quattretv-archive@.service \
        deploy/storage/quattretv-archive-cleanup.{service,timer} /etc/systemd/system/
sudo cp deploy/storage/nginx-archive.conf /etc/nginx/conf.d/   # o incluirlo en el server{}
sudo systemctl daemon-reload
sudo systemctl enable --now quattretv-archive-cleanup.timer

# Un fichero por canal, igual que los EnvironmentFile del CDN:
echo 'SRC=udp://239.0.0.1:1234' > /home/quattre/archivo/12   # 12 = id del canal
sudo systemctl enable --now quattretv-archive@12
```

Para comprobar que el enganche está bien, desde el middleware:

```bash
python manage.py comprobar_grabadores
```

Dice si el grabador pide sus tareas, si responde por HTTP y si el archivo de
cada canal migrado tiene segmentos recientes.

El detalle de lo que hace la unidad, por si hay que tocarla a mano — un ffmpeg
por canal, el mismo patrón que ya corren cdn10/cdn11 pero escribiendo a disco
en vez de a `/dev/shm`:

```bash
ffmpeg -hide_banner -loglevel warning \
  -i 'udp://239.0.0.1:1234?fifo_size=1000000&overrun_nonfatal=1' \
  -c copy -f hls \
  -hls_time 6 -hls_list_size 0 -hls_flags append_list+program_date_time \
  -strftime 1 \
  -hls_segment_filename '/srv/archive_hls/<ch_id>/%Y%m%d-%H%M%S.ts' \
  /srv/archive_hls/<ch_id>/index.m3u8
```

`-c copy`: no recodifica, solo reempaqueta (~2 % de un core por canal). La
retención se hace por antigüedad de fichero, no con `delete_segments`:

```bash
find /srv/archive_hls -name '*.ts' -mmin +$((168*60)) -delete
```

nginx solo tiene que servir el directorio y **listarlo en JSON**, que es de
donde el middleware saca el índice (no hay fichero de índice que mantener):

```nginx
location /archive_hls/ {
    alias /srv/archive_hls/;
    autoindex on;
    autoindex_format json;
}
```

### El cambio, canal a canal

```bash
# 1. Arrancar el ffmpeg nuevo del canal (arriba). Durante unos minutos graban
#    los dos: es lo que evita que quede un hueco.
# 2. Ver qué haría, sin tocar nada:
python manage.py migrar_archivo_hls 101 --simular
# 3. Hacerlo: marca el canal y para el dumpstream antiguo.
python manage.py migrar_archivo_hls 101
# 4. Comprobar el catchup en una LG y en un deco.
# 5. Si algo va mal:
python manage.py migrar_archivo_hls 101 --revertir
```

Al revertir, el canal vuelve a aparecer en la lista de tareas y el grabador
antiguo lo recoge solo en su siguiente ciclo (5 min). Las grabaciones de cliente
llevan su propio campo `container`, así que las hechas en TS se siguen
reproduciendo después de activar `records_hls` en el servidor.

**Los CDN no se tocan en ningún momento**: siguen dando el directo igual.
