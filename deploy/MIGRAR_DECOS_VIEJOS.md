# Migrar los decos viejos sin tocarlos

Analisis del 19/08/2026 sobre el registro real de `iptv1` (185.25.27.50), la
maquina del Stalker viejo, que lleva 299 dias en marcha.

## La buena noticia: no hay que tocar ningun deco

La preocupacion razonable es que los decos llevan la direccion en el firmware y
haya que ir uno por uno. **No hace falta.** Lo que piden es esto:

```
http://iptv1.quattre.com/stalker_portal/server/load.php?type=itv&action=set_last_id&...
Referer: http://iptv1.quattre.com/stalker_portal/c/
User-Agent: ... MAG200 stbapp ver: 4 rev: 734 ...
```

Es **el mismo protocolo que ya habla la plataforma nueva** — `type=` mas
`action=` — y ademas en una ruta que ya tenemos publicada. Comprobado en vivo
contra `https://iptv2.quattre.com/stalker_portal/server/load.php`:

| peticion | respuesta de la plataforma nueva |
|---|---|
| `type=watchdog&action=get_events` | `{"js":{"result":true}}` |
| `type=stb&action=handshake` | `{"js":{"token":"...","not_valid":1}}` |
| `type=itv&action=set_last_id` | `{"js":{"error":"Unknown action"}}` |
| `type=weather&action=get_current` | `{"js":{"error":"Unknown type/action"}}` |

Asi que la migracion consiste en **cambiar lo que hay detras del nombre**, no en
cambiar los decos: se apunta `iptv1.quattre.com` a la maquina nueva y los 668
decos se mudan solos.

**Ojo:** los decos hablan **http**, no https. La plataforma nueva tiene que
seguir sirviendo el puerto 80 para ellos. Convive sin problema con el https que
usan las apps de television.

## Cuanto falta: el 20,6 %

De **252.079 peticiones** en un dia, hechas por **668 decos distintos**:

- **200.083 (79,4 %) ya las contesta** la plataforma nueva.
- **51.996 (20,6 %) no.**

Y de ese hueco, **31.670 son una sola cosa trivial**: `weather`.

### Tipos que no existen (hay que crear el manejador)

| tipo | peticiones/dia | acciones |
|---|---|---|
| `weather` | 31.670 | `get_current` |
| `radio` | 166 | `get_fav_ids`, `get_all_fav_radio`, `get_ordered_list` |
| `downloads` | 162 | `save`, `get_all` |
| `remote_pvr` | 89 | `get_active_recordings`, `get_ordered_list`, `del_rec`, `create_link`, `start_rec_now` |
| `tvreminder` | 81 | `get_all_active` |
| `media_favorites` | 81 | `get_all` |

### Acciones sueltas que faltan

| tipo | accion | peticiones/dia |
|---|---|---|
| `itv` | `set_last_id` | 13.325 |
| `itv` | `get_epg_info` | 2.473 |
| `stb` | `set_volume` | 1.773 |
| `itv` | `set_fav_status` | 629 |
| `itv` | `set_played` | 614 |
| `epg` | `get_data_table` | 136 |
| `tv_archive` | `set_played` | 95 |
| `stb` | `get_tv_aspects` | 81 |
| `stb` | `get_preload_images` | 81 |
| `itv` | `get_fav_ids` | 81 |
| `itv` | `get_all_fav_channels` | 81 |
| `tv_archive` | `set_played_timeshift` | 74 |
| `tv_archive` | `update_played_timeshift_end_time` | 72 |
| `tv_archive` | `update_played_end_time` | 53 |
| `stb` | `get_ad` | 52 |
| `tv_archive` | `get_link_for_channel` | 36 |
| `epg` | `get_all_program_for_ch` | 36 |
| `stb` | `set_aspect` | 32 |
| `tv_archive` | `get_next_part_url` | 22 |
| `stb` | `get_storages` | 1 |

La mayoria son de anotar y decir que si (`set_volume`, `set_last_id`,
`set_aspect`, `set_played`), no de inventar nada. `weather` puede devolver una
respuesta fija: el deco solo la pinta en una esquina.

## Otras rutas que piden

Ademas de `load.php`, en el registro aparecen:

```
/stalker_portal//server/api/chk_tmp_archive_link.php   6.455/dia  (doble barra)
/stalker_portal/api/tv_archive/record1b                2.788/dia
/stalker_portal/api/tv_archive/storage1                   95/dia
/stalker_portal/server/api/load_js.php                    88/dia
/stalker_portal/c/  y sus .js                             ~90/dia
```

Las de `api/tv_archive/` son los grabadores pidiendo tareas — ver
[[ministra-grabacion-storage-contrato]]. La doble barra de
`chk_tmp_archive_link.php` hay que respetarla tal cual: la manda el deco.

## Orden sensato para hacerlo

1. Tapar el hueco del 20,6 % (empezando por `weather`, `itv/set_last_id` y
   `stb/set_volume`, que son el 92 % de lo que falta).
2. Volver a medir contra este mismo registro hasta llegar al 100 %.
3. Conectar los grabadores (ver `deploy/README.md`).
4. Cambiar `iptv1.quattre.com` a la maquina nueva, fuera de horario punta.
5. Dejar la maquina vieja encendida unos dias: si algo sale mal, se devuelve el
   DNS y los decos vuelven solos.

## Como repetir la medida

En `iptv1`, sin tocar nada:

```bash
grep -o 'type=[a-z_]*&action=[a-z_]*' /var/log/nginx/access.log \
  | sort | uniq -c | sort -rn
```
