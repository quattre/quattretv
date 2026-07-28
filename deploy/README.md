# Puesta en marcha de EPG y grabaciones

Nada de esto reinventa el grabador: seguimos usando `dumpstream` de Ministra en
record1 y storage1. Lo único que cambia es quién les dice qué grabar.

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
