# Self-Checklist — QuattreTV (com.quattre.tv 1.1.0)

El formulario de verdad se descarga de Seller Lounge y se sube relleno. Esto es
el material para rellenarlo: cada punto con su respuesta y **con qué se ha
comprobado**, para no marcar casillas a ojo. LG rechaza los autochequeos que
estan todos en verde sin haber probado nada, y ademas si marcas algo como
probado y falla en su revision, pierdes credibilidad para el resto del envio.

**Leyenda:** ✅ comprobado · ⏳ falta probarlo en la television · ❌ no cumple

---

## 1. Paquete y metadatos

| # | Punto | Estado | Con qué se ha comprobado |
|---|---|---|---|
| 1.1 | El `.ipk` contiene solo los ficheros de la app | ✅ | Listado del paquete: 5 ficheros y `packageinfo.json`, 22 KB. Sin fuentes, sin scripts, sin documentacion |
| 1.2 | No se distribuye ninguna credencial dentro del paquete | ✅ | `empaquetar.sh` aborta si se cuela cualquier fichero de mas. Antes el paquete llevaba dentro `instalar_tv.sh` con la contraseña del modo desarrollador |
| 1.3 | `appinfo.json` con id, version, vendor y titulo correctos | ✅ | `com.quattre.tv`, 1.1.0, Quattre Internet SL |
| 1.4 | No se piden permisos que no se usan | ✅ | `requiredPermissions` retirado. La app no llama a ninguna API de webOS |
| 1.5 | Resolucion declarada 1920x1080 | ✅ | `appinfo.json` |
| 1.6 | Iconos con las medidas y el formato que exige LG | ✅ | 80x80, 130x130, splash 1920x1080 y 400x400 para la tienda. Fondo opaco, margen interior, diseño plano |

## 2. Red y seguridad

| # | Punto | Estado | Con qué se ha comprobado |
|---|---|---|---|
| 2.1 | Todo el contenido de red por HTTPS | ✅ | Portal `https://iptv2.quattre.com`, certificado Let's Encrypt con renovacion automatica |
| 2.2 | El video tambien por HTTPS | ✅ | cdn10 y cdn11 con certificado desde el 24/08/2026. Comprobado desde fuera: playlist y un segmento de 7 MB por https |
| 2.3 | Ninguna llamada suelta en http | ✅ | Revisadas las plantillas del portal (0 coincidencias) y las 83 URLs de canal y los logos |
| 2.4 | No se recogen datos personales desde la app | ✅ | La app solo guarda en la television la direccion del servidor que respondio |
| 2.5 | URL de politica de privacidad | ✅ | `https://quattre.com/avisolegal/`, en el dominio de la empresa y junto al aviso legal general. Cubre todas las apps de QuattreTV, no solo la de LG, y esta en castellano e ingles |

## 3. Comportamiento cuando algo falla

| # | Punto | Estado | Con qué se ha comprobado |
|---|---|---|---|
| 3.1 | Television sin internet: aviso entendible, no pantalla negra | ⏳ | Implementado y con banco de pruebas (`prueba_conexion.js`, 5 casos). **Falta repetirlo en la television** |
| 3.2 | Servidor apagado: mismo comportamiento | ⏳ | Igual que el anterior |
| 3.3 | Reintenta solo, sin que el usuario pulse nada | ✅ | Esperas de 2, 4, 8 y 15 s, y reintento inmediato al recuperarse la red |
| 3.4 | El boton de reintentar tiene el foco | ✅ | `focus()` al mostrarlo; responde al OK del mando |
| 3.5 | Un canal que no arranca no deja la app colgada | ✅ | Se avisa en pantalla y se vuelve a la lista |

## 4. Navegacion con el mando

| # | Punto | Estado | Con qué se ha comprobado |
|---|---|---|---|
| 4.1 | Toda la app se usa sin puntero ni teclado | ⏳ | El codigo maneja flechas, OK, atras y numeros en todas las pantallas. **Falta el recorrido completo en la television** |
| 4.2 | El boton atras hace algo sensato en cada pantalla | ✅ | `disableBackHistoryAPI: true`; lo gestiona la app y siempre lleva hacia la lista de canales |
| 4.3 | No hay ninguna pantalla sin salida | ✅ | Revisado el manejador de teclas: todas las vistas atienden atras |
| 4.4 | Se sale de la app con HOME | ⏳ | Lo gestiona webOS. **Falta probarlo** |
| 4.5 | El teclado en pantalla se abre en los campos de texto | ⏳ | Implementado en la pantalla de acceso. **Falta probarlo** |

## 5. Contenido

| # | Punto | Estado | Con qué se ha comprobado |
|---|---|---|---|
| 5.1 | Hay contenido para adultos y se declara | ✅ | Declarado en el UX Scenario |
| 5.2 | Control parental con PIN | ✅ | El servidor no entrega la direccion del canal bloqueado; el PIN no es una cortina de la app |
| 5.3 | El revisor puede comprobar el control parental | ✅ | Canal 29 (Dark) marcado como +18 y PIN 1234 en la cuenta de revisores. Comprobado contra el servicio en marcha en cinco fases: llega con la direccion vacia, sin PIN devuelve error, PIN malo se rechaza, PIN bueno se acepta, y solo entonces entrega la URL |
| 5.4 | Ninguna opcion del menu lleva a una pantalla vacia | ✅ | La cuenta de revisores paso a una tarifa de solo TV: Peliculas, Series y Mis grabaciones ya no aparecen |
| 5.5 | Ninguna funcion ofrecida esta rota | ✅ | El archivo ya no se anuncia si no hay grabador dando señales. Antes lo anunciaban 81 canales sin haberlo |
| 5.6 | No hay publicidad, compras ni contenido de usuarios | ✅ | |

## 6. Cuenta para la revision

| # | Punto | Estado | Con qué se ha comprobado |
|---|---|---|---|
| 6.1 | Usuario y contraseña entregados | ✅ | `lgreview` / ver `ACCESOS.md` (copia local, fuera del repositorio) |
| 6.2 | Sin fecha de caducidad | ✅ | Comprobado en la ficha: caducidad vacia |
| 6.3 | Con acceso a todo el contenido que ofrece la app | ✅ | 83 canales y guia |
| 6.4 | Varios equipos permitidos | ✅ | 5 equipos, 2 emisiones simultaneas |

---

## Lo que falta antes de enviar

1. **La tanda de pruebas en la television** (los ⏳): sin internet, con el servidor
   apagado, recorrido completo solo con el mando, salir con HOME y el teclado en
   pantalla. Es una tarde y evita el rechazo mas tonto.
2. **Capturas de pantalla** para la ficha de la tienda, que se hacen con la app
   corriendo en la television. Las medidas exactas salen en Seller Lounge.

Y una revision que no bloquea el envio pero conviene hacer: que Marta Hernandez
Acamer, la delegada de proteccion de datos, mire la politica publicada. Los
plazos de facturacion salen del Codigo de Comercio y de la Ley General
Tributaria, pero los doce meses de los registros de acceso son una decision de
la casa.
