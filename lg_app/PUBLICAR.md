# Publicar QuattreTV en la LG Content Store

Mientras la app se instale en modo desarrollador **caduca cada 50 horas** y al
caducar desaparece de la tele. Publicarla lo resuelve del todo: deja de caducar,
se instala desde la tienda de la propia television sin ordenador de por medio, y
vale para la LG de cualquier cliente, no solo para la de pruebas.

## El bloqueo que habia ya no existe

LG exige **HTTPS** para todo el contenido de red. La app apuntaba a
`http://iptv1.quattre.com:8000` y eso hacia imposible enviarla. Ahora apunta a
`https://iptv2.quattre.com`, con certificado que se renueva solo, asi que ese
requisito esta cumplido.

## Lo que ya esta listo

- **Paquete**: `com.quattre.tv_1.1.0_all.ipk`, generado con `ares-package`.
- **Iconos**: `icon.png` (80x80), `largeIcon.png` (130x130), `splash.png`
  (1920x1080) y `icon_tienda_400.png` (400x400). Se rehacen todos con
  `generar_iconos.py`.

  Lo que exige LG, comprobado en su documentacion:
  - **El fondo NO puede ser transparente.** Si se deja, la television pinta de
    negro lo que quede fuera del dibujo — es lo que pasaba al redondear las
    esquinas.
  - **Minimo 5 px de margen** interior. El generador deja el 11 % del lado, que
    son 8 px en el de 80.
  - **Diseño plano, sin efectos visuales**, y que no toque los bordes.
  - En la tienda el logotipo **se muestra en una caja cuadrada**, asi que no
    tiene sentido redondear nada.
  - El de **400x400 no va dentro del paquete**: se sube aparte en Seller Lounge
    y es el que se ve en la tienda, redimensionado por ellos.

  **Desviacion consciente de la especificacion:** LG documenta `icon.png` a
  80x80, pero la television pinta ESE en la fila de aplicaciones y a su tamaño
  real. Al lado de los iconos del sistema, que llenan la baldosa de 130, el
  nuestro se veia al 61 % con negro alrededor — y 80/130 es exactamente 0,61.
  Por eso se genera tambien a 130. **Si el envio a la tienda lo rechaza por el
  tamaño**, hay que volver a 80x80 para el paquete que se sube (en la tienda no
  se nota, porque alli usan el de 400x400).
- **HTTPS** en todo el contenido de red.
- **Comportamiento cuando falla la red**: la app pregunta al servidor antes de
  entrar y, si no contesta, enseña un aviso entendible y un boton de reintentar.
  LG prueba este caso en la revision y es de los motivos de rechazo mas
  frecuentes.
- **Manejo del mando**: el boton de reintentar recibe el foco, que es lo que
  responde al OK del mando.

## Lo que hace falta y solo puedes conseguir tu

1. **Cuenta de LG Seller Lounge** (seller.lgappstv.com). Es gratis, no cobran por
   enviar, pero hay que darse de alta como empresa y ahi es donde estan las
   especificaciones exactas de las imagenes de tienda, que no son publicas.
2. **URL de politica de privacidad**. La piden siempre. Puede ser una pagina en
   quattre.com.
3. **Clasificacion de contenido**. Ojo con esto: la plataforma tiene canales para
   adultos. Hay control parental por PIN, y conviene decirlo explicitamente en el
   documento de escenario de uso, porque si lo detectan sin declararlo es rechazo
   directo.
4. **Cuenta de prueba para los revisores**. Van a necesitar entrar. Hay que darles
   un usuario y contraseña con tarifa completa, y **que no caduque** mientras
   dure la revision (en la ficha del usuario, dejar la fecha de caducidad vacia).

## Los dos documentos obligatorios

Estos dos se rechazan si faltan o van flojos, asi que merece la pena dedicarles
tiempo:

- **UX Scenario**: como se usa la app, pantalla por pantalla, con que botones del
  mando se navega. Cuanto mas detallado, mas facil se lo pones al que la prueba.
  Aqui es donde hay que explicar el control parental.
- **Self-Checklist**: el formulario de LG con los resultados reales de haber
  probado la app. Hay que rellenarlo de verdad, no marcarlo todo.

## Como va la revision

Tres fases: pretest, prueba de funcionamiento y prueba de contenido. Suele tardar
entre una y dos semanas, y para una app con algo de chicha es normal que haya que
corregir y reenviar dos o tres veces. Cada actualizacion posterior pasa otra vez
por aprobacion.

## Antes de enviar, repasar

- [ ] Probar con la television **sin internet**: tiene que salir el aviso, no una
      pantalla en negro.
- [ ] Probar con el **servidor apagado**: mismo caso.
- [ ] Recorrer toda la app **solo con el mando**, sin raton ni teclado, y que no
      haya ninguna pantalla de la que no se pueda salir.
- [ ] Comprobar que el boton **atras** del mando hace algo sensato en cada
      pantalla (`disableBackHistoryAPI` esta en `true` en el `appinfo.json`, asi
      que lo gestiona la propia app).
- [ ] Ver que todo el contenido de red va por **https**, sin ninguna llamada
      suelta en http.
- [ ] Dejar la cuenta de prueba de los revisores **sin fecha de caducidad**.

## Fuentes

- [App Approval Process - webOS TV Developer](https://webostv.developer.lge.com/distribute/app-approval-process)
- [App Ecosystem - webOS TV Developer](https://webostv.developer.lge.com/distribute/app-ecosystem)
- [LG Seller Lounge](https://seller.lgappstv.com/seller/main/Main.lge)
