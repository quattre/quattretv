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

## Estado a 07/09/2026

Probado entero en un Samsung TU32H5005 propio (Tizen 8.0) con el depurador
enchufado. Funciona: los 80 canales, el video a 1920x1080 con sonido, los
cuatro botones de color, el atras, la guia, la ficha, las emisoras de radio,
la pantalla completa y el acceso.

**El acceso ya no depende del teclado del televisor.** El de Tizen va a rachas
-unas veces sale y escribe, otras sale y no llega ni una letra al campo- asi que
en Samsung la aplicacion dibuja el suyo: solo necesita flechas y OK. En webOS y
en los decos se sigue usando el del aparato, que ahi funciona.

**Material del envio**, en `/home/sergio/envio-samsung/`:

| Fichero | Que es |
|---|---|
| `capturas/` | ocho capturas a 1920x1080, con imagen real del canal |
| `UX_SCENARIO_samsung.pdf` | el documento para los revisores, 12 paginas |

Se rehacen con:

```
python3 lg_app/capturas_navegador.py https://iptv2.quattre.com/quattretv/stb/ <MAC> capturas
python3 lg_app/montar_video_en_capturas.py capturas <fotograma.png>
CLAVE_PRUEBA=... python3 lg_app/generar_ux_scenario.py capturas/con-video salida.pdf samsung
```

## Lo que falta, y necesita la cuenta de Samsung

Esto no se puede hacer desde aqui, hace falta entrar en el Seller Office:

1. **Dar de alta la aplicacion** en https://seller.samsungapps.com y anotar el
   **identificador de paquete** que asignen: diez caracteres. Va en dos sitios
   de `samsung_app/config.xml`, lineas 23 y 24, donde ahora pone `QuattreTV0`,
   que es de mentira.
2. **Certificado de distribucion de Samsung.** El que hay es autofirmado: vale
   para el televisor en modo desarrollador, no para publicar. Se saca del
   asistente de certificados de Tizen Studio con la cuenta de la empresa.
   **Ojo con el asistente**: hay que elegir el de *Samsung*, no el de *Tizen* --
   el de Tizen no pide DUID y no sirve. Y el de distribucion va atado a los
   DUID de la lista; el de la tienda, no.
3. Con las dos cosas, reempaquetar y firmar:
   `PERFIL_FIRMA=<perfil> samsung_app/empaquetar.sh`

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
