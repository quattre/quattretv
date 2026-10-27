# Plan de migración: de Ministra a la plataforma nueva

Estudio del 27/10/2026, hecho leyendo en solo lectura la base de datos de
Ministra (`stalker_db` en iptv1, SSH 2101) y los dos grabadores. No se cambió
nada en ninguna máquina.

Complementa a `MIGRAR_DECOS_VIEJOS.md` (qué piden los MAG y qué falta por
contestar) y a `README.md` (cómo se conectan los grabadores y el archivo HLS).

## 0. Decisión: dos grabadores en paralelo (27/10/2026)

Los grabadores se mantienen. En record1 se instala **una copia del grabador**
(`deploy/storage/copia_grabador.sh`) que obedece a la plataforma nueva y graba en
su propia carpeta (`records_quattretv/`). El de Ministra sigue igual. Las
grabaciones antiguas se copian como fichas (`importar_ministra`) y se reproducen
desde su carpeta de siempre, solo leyendo; no se pueden borrar desde la nueva
mientras Ministra mande. Las cuentas se copian cada noche y Ministra sigue siendo
la buena hasta el cambio.

Orden para apagar Ministra sin que se pare nada: el grabador nuevo funcionando →
storage1 apuntando a la nueva (le da la misma lista de canales, con los id de
Ministra) → grabaciones pendientes pasadas → solo entonces se apaga Ministra.

Hallazgos al montarlo:
- La plataforma nueva **sí llega a los grabadores** por sus puertos públicos
  (storage1 `185.25.27.50:2142`, record1 `:2222`): no hace falta segunda tarjeta.
- **record1 sirve los `.mpg` por el 2222 sin comprobar firma**: con la dirección
  se descarga cualquier grabación. Ya pasa hoy con Ministra. Pendiente de cerrar.
- dumpstream avisa con un `PUT` y la nueva solo leía `POST`: las grabaciones se
  habrían quedado en "grabando". Arreglado.
- El aviso de dumpstream va siempre por http al puerto 80; la copia se parchea
  para hablar https.
- Hasta que el grabador escriba HLS, las grabaciones solo se ofrecen a los MAG:
  la LG no abre el MPEG-TS.

## 1. Qué hay que mover

| Qué | Cuánto | Comentario |
|---|---|---|
| Cuentas | **949** (930 activas) | 788 conectadas en los últimos 2 días, 864 en 30 |
| MAC | 917 | 32 cuentas sin MAC |
| Decos | MAG540 377, MAG256 209, MAG520 202, MAG322 101, MAG524 15, MAG420 12 | |
| Tarifas | 5 | `default_full` 899, `test` 19, `defaul_full_sin_dark` 15, tablet 3+1, sin tarifa 12 |
| Favoritos | 364 cuentas | JSON con los id **internos** de canal de Ministra |
| PIN parental | 0 propios | Los 949 tienen el `0000` de fábrica: no hay nada que migrar |
| Caducidad, saldo, bloqueo | nada | Ministra no lleva facturación; solo `status` (1 = apagada, 19 cuentas) |
| Canales | 66 (65 activos) | id internos 2–128, números 1–67; **ninguno coincide id con número** |
| Radios | 18 | |
| VOD | 0 | No hay videoclub que migrar |
| Archivo (catchup) | 49 canales grabando en storage1, 7 días | Solo **9** tienen el catchup activado para el cliente |
| Grabaciones de cliente | **404** de **166** clientes, 12.797 h, **1,8 TB** en record1 | De 27/10/2025 a hoy; 8 en curso y 1 programada al mirarlo |

### Detalles que condicionan el diseño

- **En Ministra, una cuenta es un deco.** El `login` es único por fila y cada
  fila tiene una sola MAC. Un cliente con dos decos tiene dos cuentas (hay 110
  nombres repetidos, que es lo que lo delata). No hay teléfonos guardados.
- **Contraseñas:** `md5(md5(contraseña) . id)`, 32 caracteres en las 949
  (`tools/auth_simple.php`). Se pueden importar tal cual con un *hasher* propio
  que las compruebe y las pase a PBKDF2 en el primer acceso. Los decos no las
  usan (entran por MAC); las necesitan las apps de LG y Samsung.
- **Las grabaciones se llaman por el id de `rec_files`**, no por el de
  `users_rec`: `<file_id>_<AAAAmmddHHMMSS>.mpg` (comprobado en las 404).
  Además hay 27 `.mpg-temp` sueltos, probablemente restos de grabaciones cortadas.
- **record1 tiene dos nombres.** Ministra lo tiene dado de alta como
  **`record1c`** (`storages`, HTTP en `185.25.27.50:2222`), pero su
  `config.php` dice `STORAGE_NAME=record1b`. El primero es el que usan las
  grabaciones; el segundo, el que pide tareas de archivo (no tiene ninguna).
- **storage1 tiene el disco raíz al 93 % (2,1 GB libres).** Es un riesgo hoy,
  con o sin migración.

## 2. El problema de fondo: los números internos de canal

El archivo de storage1 está en `archive/<ch_id>/` y las grabaciones apuntan a
`ch_id`, y los dos usan el **id interno de Ministra**. La plataforma nueva tiene
sus propios id. Sin una tabla de correspondencia, el catchup saldría de otro
canal y los favoritos y las grabaciones importadas quedarían colgando.

**Propuesta:** campo `Channel.ministra_id`, rellenado por una orden que empareje
por nombre y número y que se revisa a mano (son 66). Con eso:
- La lista de tareas de `tv_archive` le manda a storage1 el `ministra_id` como
  `ch_id`, y el archivo TS sigue grabando en las mismas carpetas: **no se pierde
  ni una hora de catchup** el día del cambio.
- `build_catchup_url` usa el `ministra_id` para el archivo TS viejo y el id
  propio para el HLS nuevo.
- Favoritos y grabaciones se traducen al importar.

## 3. Lo que hay que construir

1. **`importar_ministra`** (orden de gestión, con `--simular`): lee
   `stalker_db` por SSH y crea, por cada cuenta:
   - un `User` con el mismo `login`, la contraseña en formato Ministra y la
     tarifa traducida;
   - un `Device` tipo `mag` con su MAC, modelo y número de serie;
   - sus favoritos, ya con los canales traducidos.
   Se puede relanzar: actualiza lo que ya existe en vez de duplicar.
2. **Hasher `ministra`**: comprueba `md5(md5(p) . id)` y se actualiza solo a
   PBKDF2 al entrar.
3. **`importar_grabaciones_ministra`**: por cada `users_rec` crea una
   `Recording` completada, `container='ts'`, `storage=record1`,
   `filename=<rec_files.file_name>`, con el canal y el cliente traducidos. Las
   futuras entran como programadas.
4. **Que el deco pueda reproducir las grabaciones viejas.** Hoy Ministra las da
   con un enlace por MAC (`remote_pvr`); la plataforma nueva construye
   `<playback_url>/<fichero>`, así que hace falta un `location` en el nginx de
   record1 que sirva `records/` con token. En LG no se verán mientras sean TS
   (ver `catchup-lg-remux-opciones`).
5. **Red:** la plataforma nueva **no llega por HTTP a los grabadores**
   (`192.168.100.x`) desde que tiene IP pública. Hace falta una segunda tarjeta
   en la red interna (lo recomendado) o redirigir dos puertos.
6. **El 21 % de peticiones que aún no se contestan** (`MIGRAR_DECOS_VIEJOS.md`):
   el tiempo (31.670 peticiones al día), `set_last_id`, `set_volume`,
   `remote_pvr`, recordatorios… Basta con que respondan algo válido; el tiempo
   puede devolver vacío.

## 4. Fases

### Fase 0: preparar, sin tocar a ningún cliente
- Liberar espacio en el disco raíz de storage1.
- Resolver la red hacia los grabadores.
- Construir lo del punto 3 y probar el import en `--simular` contra la base real.
- Rellenar y revisar `ministra_id` de los 66 canales.

### Fase 1: piloto con 5–10 decos de confianza
- Importar solo esas cuentas.
- En cada deco, cambiar a mano la URL del portal a la plataforma nueva
  (Ajustes → Servidores → Portales). Volver atrás es poner la vieja.
- Una semana de uso real. Las grabaciones del piloto se pueden mandar a record1
  sin tocar su config (el recurso `recorder` no valida credenciales; el aviso de
  fin iría a la vieja, y lo compensa `reconcile_recordings`).

### Fase 2: el cambio, de madrugada
1. Congelar altas y bajas en Ministra ese día.
2. Import final de cuentas, favoritos y grabaciones.
3. En storage1 y record1, cambiar `API_URL` y `PORTAL_URL` a la plataforma nueva.
4. Cambiar el `proxy_pass` del vhost de iptv1 a la plataforma nueva y recargar
   nginx. Los decos no se tocan: siguen pidiendo `iptv1.quattre.com`.
5. Comprobar: entrada de decos en el registro, directo, catchup de los 9
   canales, una grabación vieja y una nueva.
6. **Vuelta atrás:** deshacer el `proxy_pass` y las dos líneas de cada
   grabador. Lo que se haya grabado en la nueva desde el cambio no estará en la
   vieja.

Elegir un momento sin grabaciones en curso; si las hay, su aviso de fin llega
a la nueva con el id de Ministra (por eso conviene importar las grabaciones
conservando `rec_files.id`).

### Fase 3: después
- Mantener Ministra encendida 2 semanas, sin servicio, por si hay que volver.
- Pasar el archivo a HLS canal a canal (`migrar_archivo_hls`), para que el
  catchup funcione también en LG. storage1 tiene 8 núcleos: ir por tandas.
- Grabaciones nuevas en HLS (`records_hls`).

## 5. Decisiones pendientes

1. **¿Unir las cuentas de un mismo cliente con varios decos?** Ministra no da
   un dato fiable para hacerlo (110 nombres repetidos, sin teléfonos). Propuesta:
   migrar 1 a 1 y unir más tarde, a mano o con un fichero del ERP.
2. **Traducción de tarifas:** `default_full` y `test` a la completa,
   `sin_dark` a la completa sin el canal adulto, las dos de tablet a… (falta
   decidirlo).
3. **¿Se conservan las grabaciones viejas?** Propuesta: sí; son 1,8 TB de 166
   clientes y record1 tiene 27 TB libres.
4. **Fecha del cambio.**
