# Marca: logotipos e imagenes de las aplicaciones

Aqui vive lo que se le pide al diseñador y lo que hace falta para las tiendas.

## El encargo

`logotipos_app_quattretv.pdf` es el documento que se envia. Pide tres cosas:

1. **El logotipo en vectorial** (SVG, AI o EPS). Es lo importante: con el se
   generan aqui todos los tamaños que pida cada tienda sin volver a molestar.
2. **Los dos rotulos que van dentro de la aplicacion**, con las medidas tomadas
   sobre un televisor de verdad.
3. **Los iconos de cada tienda**, con lo que ya se usa en LG, lo que falta por
   enviar a Samsung y lo previsto para Android TV.

## Por que las medidas son estas

Los dos rotulos de la aplicacion son **texto**, no imagenes: tipografia Antonio
en `#81BA26`. Las cifras del PDF salen de medir esos rotulos en un Samsung
TU32H5005 a 1920x1080, no de leer el CSS, porque el tamaño final depende de la
tipografia que acabe cargando el televisor.

| Donde | Ocupa hoy | Sitio disponible |
|---|---|---|
| Pantalla de acceso | 425 x 117 px | 450 x 120 px |
| Cabecera del portal | 182 x 46 px | 440 x 60 px |

La cabecera se ve pequeña porque usa 182 px de los 440 que tiene. El limite de
la derecha lo marca la etiqueta verde con el numero de canales.

## Rehacer el PDF

```
weasyprint marca/logotipos_app_quattretv.html marca/logotipos_app_quattretv.pdf
```

Las capturas de `capturas/` salieron del televisor con el depurador enchufado
(`Page.captureScreenshot`), asi que son la pantalla real y no un montaje.

## Cuando llegue el logotipo

Los rotulos se cambian en las plantillas: `h1` en `templates/stb/loader.html` y
`.logo` en `templates/stb/portal.html`. Los iconos de LG estan en `lg_app/`
(`icon.png` 80x80, `largeIcon.png` 130x130, `splash.png` 1920x1080) y el de
Samsung lo toma `samsung_app/empaquetar.sh` de esa misma carpeta.
