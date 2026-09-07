# La app para televisores Samsung (Tizen)

Es la misma idea que la de LG: un envoltorio fino que carga el portal desde
nuestros servidores. **El cargador, el icono y el splash se toman de `lg_app/`**,
no se duplican aquí — dos copias del mismo fichero acaban separándose sin que
nadie se dé cuenta. Lo único propio de Samsung es `config.xml`.

Eso significa que **todo lo que se arregla en el portal llega a las dos apps
sola**, sin reempaquetar ni volver a pasar por ninguna tienda.

## Lo que ya está hecho

- `config.xml` con los permisos que hacen falta, en particular
  **`tv.inputdevice`**: sin él Tizen no deja registrar los botones de color ni
  el de información, y la aplicación no los recibe.
- El portal registra esas teclas al arrancar (`pedirTeclasTizen`) y entiende el
  atrás de Samsung, que es el **10009** y no el 461 de LG.
- El cargador ya identifica el aparato como `samsung` y el middleware lo acepta.
- El filtro de canales por tipo de aparato ya tiene su casilla de Samsung, así
  que el canal +18 se puede excluir igual que en LG si su tienda lo exige.

## Lo que falta, por orden

1. **Cuenta de Samsung Developer** y alta de la app en el Seller Office. De ahí
   sale el identificador de paquete —diez caracteres— que hay que poner en
   `config.xml`, donde ahora dice `QuattreTV0`, que es de mentira.
2. **Tizen Studio** en el equipo, para empaquetar y firmar. Hace falta un
   certificado de autor y otro de distribución, los dos se sacan desde el propio
   Tizen Studio con la cuenta de Samsung.
3. **Probar sin comprar televisor**: Samsung tiene un *Remote Test Lab* gratuito
   con aparatos reales por navegador, con captura de pantalla, grabación y
   audio. Es mejor que lo que ofrece LG.
4. **Comprar una Samsung barata antes de enviar.** Lo de LG lo demostró: los
   siete fallos que aparecieron —el teclado que no se abría, el vídeo que no
   arrancaba al encender, la radio en negro— no habrían salido en ningún
   simulador. Salieron con el mando en la mano.
5. Rehacer las **capturas** en un Samsung y adaptar el **UX Scenario**, que es
   casi todo reaprovechable.

## Lo que hay que comprobar de su tienda

Antes de dar por bueno lo que decidimos para LG, hay que mirar si Samsung tiene
las mismas reglas en dos puntos concretos:

- ~~**Contenido para adultos.**~~ **Resuelto el 07/09/2026: Samsung es más
  estricto que LG.** Su política de clasificación por edades dice que *«las
  aplicaciones no pueden contener contenido violento o pornográfico»*, sin
  excepciones y **sin la vía del contrato aparte que sí ofrece LG**. Sí admite
  temática adulta en la categoría 18+ —referencias al sexo, comportamiento
  sexual sin detalle—, pero pornografía no, con ninguna clasificación.

  El canal 29 ya está oculto para `samsung` además de para `lg`: un MAG ve 81
  canales y una LG o una Samsung, 80. Se cambia con un clic en la ficha del
  canal, en `/channels/`.
- **Caducidad del modo desarrollador.** El de LG dura 50 horas y al caducar
  **borra la app del televisor**. Conviene saber si el de Samsung hace lo mismo
  antes de dejar pruebas a medias.

## Empaquetar

```
samsung_app/empaquetar.sh
```

Deja la carpeta lista en `dist/` y escribe los comandos de Tizen Studio. El
empaquetado en sí no se puede hacer aquí porque esa herramienta no está
instalada.
