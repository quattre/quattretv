# Envío de QuattreTV a la LG Content Store

Todo lo que hay que subir a Seller Lounge está en esta carpeta. Abajo, los datos
listos para copiar y pegar en cada campo.

---

## Los ficheros

| Fichero | Dónde va |
|---|---|
| `com.quattre.tv_1.1.0_all.ipk` | El paquete de la app |
| `icon_tienda_400.png` | Icono de la tienda, 400×400. **Es el que se ve en la baldosa del televisor**, no el que va dentro del paquete |
| `capturas/` | Seis capturas a 1920×1080, sacadas de la app corriendo en un televisor real |
| `UX_SCENARIO.md` | Documento obligatorio de escenario de uso |
| `AUTOCHEQUEO.md` | Material para rellenar el Self-Checklist de LG |
| `POLITICA_PRIVACIDAD.md` | Referencia; la política ya está publicada, ver abajo |

---

## Datos de la ficha

| Campo | Valor |
|---|---|
| **Nombre** | QuattreTV |
| **ID** | com.quattre.tv |
| **Versión** | 1.1.0 |
| **Vendedor** | Quattre Internet S.L. |
| **NIF** | B98168206 |
| **Domicilio** | C/ Alguixós 5, 46138 Rafelbunyol (València), España |
| **Teléfono** | 961 126 346 |
| **Contacto** | info@quattre.com |
| **Categoría** | Vídeo / Entretenimiento |
| **Idioma** | Español (es-ES) |
| **Precio** | Gratuita. No hay compras dentro de la app |
| **Política de privacidad** | https://quattre.com/avisolegal/ |

## Cuenta para los revisores

| | |
|---|---|
| **Usuario** | `lgreview` |
| **Contraseña** | ver `ACCESOS.md` (copia local, fuera del repositorio) |
| **Caducidad** | Ninguna |
| **Equipos** | 5, con 2 emisiones a la vez |
| **PIN parental** | `1234` |
| **Canal bloqueado para probarlo** | 29, «Dark» |

Ponlo también en las notas para el revisor, junto con esto:

> El canal 29 está clasificado para adultos y pide PIN (1234). El 30, «Dark Sin
> X», es el mismo canal sin ese contenido y no pide PIN. Mientras no se
> introduce el PIN, el servidor no entrega la dirección del canal al televisor.

## Clasificación de contenido

**Declarar que hay contenido para adultos.** Hay un canal +18 protegido con PIN
parental. Está explicado en el punto 6 del `UX_SCENARIO.md`.

No lo dejes sin declarar: si lo detectan por su cuenta es rechazo directo, y es
lo único de todo el envío que **no** se puede corregir después sin volver a
pasar por revisión.

---

## Antes de darle a enviar

De la lista de `AUTOCHEQUEO.md` quedan cuatro puntos que **solo se pueden
comprobar con la televisión delante**, y son de los que LG prueba:

- [ ] Abrir la app **sin internet**: tiene que salir el aviso con el botón de
      reintentar, nunca una pantalla en negro. Al volver la red debe entrar sola
      sin tocar el mando.
- [ ] Lo mismo **con el servidor apagado**.
- [ ] Recorrer **toda la app solo con el mando**, sin que haya ninguna pantalla
      de la que no se pueda salir, y que el botón **atrás** responda en todas.
- [ ] Salir con **HOME**, y probar el **teclado del PIN apuntando con el Magic
      Remote** (los mandos nuevos de LG no traen teclas numéricas).

Rellena el Self-Checklist con lo que salga de verdad. Marcarlo todo en verde sin
haberlo probado es de las cosas que peor sientan: si algo falla en su revisión,
pierdes credibilidad para el resto del envío.

---

## Cómo va después

Tres fases: pretest, prueba de funcionamiento y prueba de contenido. Entre una y
dos semanas, y es normal tener que corregir y reenviar un par de veces.

**Lo importante para no agobiarse:** el portal, los canales, la guía, el archivo
y el videoclub se cambian cuando quieras **sin volver a pasar por la tienda** —
la app es solo un lanzador que carga el portal, y `/ping` le dice dónde está.
Solo reenviar el `.ipk` pasa otra vez por revisión.

La excepción es la clasificación de contenido. Por eso se declara ahora.
