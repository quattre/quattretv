# Accesos y datos de las apps de QuattreTV

**Este fichero está fuera del repositorio a propósito.** Vive en
`/home/sergio/envio-lg/`, que no es un git, así que nada de esto se sube a
GitHub. Si algún día se mueve, que no acabe dentro de `quattretv/`.

Última revisión: 31/08/2026.

---

## LG — publicación

| | |
|---|---|
| **Portal de vendedores** | https://seller.lgappstv.com |
| **Cuenta** | *(la de LG de Sergio — rellenar)* |
| **Contraseña** | *(rellenar)* |
| **App ID** | `com.quattre.tv` |
| **Versión enviada** | 1.1.0 |
| **Documentación para desarrolladores** | https://webostv.developer.lge.com |
| **Consultas a LG** | Seller Lounge → 1:1 Q&A |
| **Correo para resultados de QA** | info@quattre.com *(añadir también el personal)* |

La misma cuenta de LG sirve para el portal de vendedores y para entrar en la app
**Developer Mode** del televisor.

## Televisor de pruebas

| | |
|---|---|
| **Modelo** | LG 32LM6380PLC (2019) |
| **Sistema** | webOS 4.5, navegador Chrome 53 |
| **IP** | 192.168.200.93 *(cambia si se resetea)* |
| **Puerto de desarrollador** | 9922, usuario `prisoner` |
| **Passphrase del modo dev** | ver `ACCESOS.md` (copia local, fuera del repositorio). Cambia al reactivar el modo |
| **Mando** | Magic Remote original, probado el 28/08/2026 |

**El Modo Desarrollador caduca cada 50 horas y al caducar el televisor borra la
app.** Hay que extender la sesión antes de dejarlo cada día.

Para instalar: `./lg_app/instalar_tv.sh` desde el repositorio.

## Cuenta de prueba para los revisores

| | |
|---|---|
| **Usuario** | `lgreview` |
| **Contraseña** | ver `ACCESOS.md` (copia local, fuera del repositorio) |
| **Caducidad** | ninguna |
| **Tarifa** | Solo TV — 5 equipos, 2 emisiones a la vez |
| **PIN parental** | `1234` *(hoy no lo pide ningún canal en LG)* |

## Cuenta de prueba para los revisores de Samsung

| | |
|---|---|
| **Usuario** | `samsungreview` |
| **Contraseña** | ver `ACCESOS.md` (copia local, fuera del repositorio) |
| **Caducidad** | ninguna |
| **Tarifa** | Solo TV — 5 equipos, 2 emisiones a la vez |
| **PIN parental** | `1234` *(hoy no lo pide ningún canal)* |

Igual que la de LG y por el mismo motivo: si los dos revisores usaran la misma
cuenta se pisarían las plazas de equipos y no se sabría quién ha entrado.

El canal +18 tampoco viaja a los televisores Samsung, mientras no se sepa si su
tienda lo prohíbe como LG. Hoy no cuesta nada — no hay ni un cliente con Samsung
— y se deshace con un clic en el panel, en la ficha del canal 29.

## Samsung — publicación

| | |
|---|---|
| **Portal de vendedores** | https://seller.samsungapps.com |
| **Documentación** | https://developer.samsung.com/smarttv |
| **Remote Test Lab** | https://developer.samsung.com/remote-test-lab (gratis, televisores reales) |
| **Identificador de paquete** | `QuattreTV0` *(provisional, hasta que Samsung asigne el suyo)* |
| **Tizen Studio** | `~/tizen-studio`, versión de consola |
| **Empaquetar** | `samsung_app/empaquetar.sh` |

## Servidores

| | |
|---|---|
| **Middleware (producción)** | `quattre@185.25.27.51`, puerto SSH **12121** |
| **Ruta de la app** | `/var/www/quattretv` |
| **Rama desplegada** | `worktree-epg-grabaciones` |
| **Recargar tras desplegar** | `kill -HUP $(systemctl show quattretv -p MainPID --value)` |
| **Portal** | https://iptv2.quattre.com |
| **CDN** | cdn10 y cdn11 `.quattre.com` |

**Ojo con el orden al desplegar:** primero sincronizar el fichero y **después**
recargar gunicorn. Al revés, Django se queda con la plantilla que hubiera en ese
instante y parece que el cambio no ha subido.

## Repositorio

| | |
|---|---|
| **GitHub** | git@github.com:quattre/quattretv.git |
| **Rama de trabajo** | `worktree-epg-grabaciones` |
| **Copia local** | `/home/sergio/quattretv/.claude/worktrees/epg-grabaciones` |

## Material del envío

Todo en esta misma carpeta, `/home/sergio/envio-lg/`:

| Fichero | Para qué |
|---|---|
| `com.quattre.tv_1.1.0_all.ipk` | paquete de 1920x1080, televisores UHD |
| `com.quattre.tv_1.1.0_all_720.ipk` | paquete de 1280x720, televisores FHD |
| `UX_SCENARIO.pdf` | Test Info → UX Scenario |
| `nota_para_el_tester_en.txt` | Test Info → Other Information |
| `AUTOCHEQUEO_que_marcar.md` | qué marcar en los 53 puntos |
| `descripcion_es.txt` / `_en.txt` | descripción de la tienda |
| `icon_tienda_400.png` | icono de la tienda |
| `splash_1920x1080.png`, `launcher_1920x1080.png` | imágenes de la ficha |
| `capturas/` | capturas de pantalla (del 25/08) |
| `privacidad_apps_es.html` / `_en.html` | lo publicado en quattre.com/avisolegal/ |

## Direcciones IP del equipo de revisión de LG

Están en `deploy/ips_revision_lg.txt` del repositorio, con la explicación. Van en
la variable `IPS_REVISION_LG` del `.env` de producción para que el límite de
intentos del login no les corte el paso.

## Otros datos de la empresa

| | |
|---|---|
| **Razón social** | Quattre Internet S.L. |
| **CIF** | B98168206 |
| **Domicilio** | C/ Alguixós 5, 46138 Rafelbunyol (València) |
| **Teléfono** | 961 126 346 |
| **Política de privacidad** | https://quattre.com/avisolegal/ |

## Certificado de firma de Samsung (pruebas)

| | |
|---|---|
| **Perfil** | `quattre` |
| **Certificado de autor** | `/home/sergio/tizen-studio-data/keystore/author/quattre_autor.p12` |
| **Contraseña** | ver `ACCESOS.md` (copia local, fuera del repositorio) |

Es autofirmado y usa el certificado de distribución que trae Tizen Studio: vale
para el Remote Test Lab y para un televisor en modo desarrollador, **no para
publicar**. Para la tienda hace falta el certificado de distribución de Samsung,
que se genera con la cuenta de la empresa.
