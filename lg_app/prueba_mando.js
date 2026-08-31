// Banco de pruebas del mando de LG sobre el portal (templates/stb/portal.html).
//
// Dos cosas que no se pueden comprobar a ojo sin la television delante:
//
//   - Las teclas del mando de LG no son las de un teclado. La de atras manda
//     461, no la 8 ni la 27, y hasta ahora no estaba atendida: el boton atras
//     del mando no hacia nada. Con disableBackHistoryAPI en true, gestionarlo
//     es cosa de la app, y es uno de los puntos que LG comprueba.
//   - El Magic Remote es un puntero. El portal no tenia ni un manejador de
//     clic, asi que apuntar y pulsar no hacia nada.
//
//   node lg_app/prueba_mando.js
const fs = require('fs');
const html = fs.readFileSync(__dirname + '/../templates/stb/portal.html', 'utf8');
const codigo = /<script[^>]*>([\s\S]*?)<\/script>/.exec(html)[1];

// ---------- la tele de mentira ----------
let elementos = {};
function elemento(id) {
    if (!elementos[id]) elementos[id] = { id, style: {}, innerHTML: '' };
    return elementos[id];
}
global.document = { getElementById: elemento, body: {}, onkeydown: null, onclick: null };
global.window = { addEventListener() {}, onresize: null, onload: null };
global.navigator = { onLine: true };
global.setTimeout = () => 0;
global.clearTimeout = () => {};
global.setInterval = () => 0;
// Un <video> de mentira al que se le puede decir cuantas veces debe fallar al
// arrancar, que es lo que hace la television recien encendida.
global.__video = {
    style: {}, src: '', arranques: 0, fallosPendientes: 0, diferido: false,
    play() {
        this.arranques++;
        if (this.fallosPendientes > 0) {
            this.fallosPendientes--;
            const v = this;
            // Con 'diferido' el fallo se guarda en vez de dispararse, para
            // poder simular un reintento que llega tarde.
            return { catch(f) { if (v.diferido) global.__pendiente = f; else f(); return this; } };
        }
        return { catch() { return this; } };
    },
    pause() {},
};
global.XMLHttpRequest = function () {
    this.open = function () {};
    this.send = function () {};
};

eval(codigo);

// Las secciones 5 y 8 sustituyen openGuide y handleKey por dobles; se
// guardan las de verdad porque la seccion 9 necesita ejecutarlas enteras.
const openGuideDeVerdad = openGuide;
const handleKeyDeVerdad = handleKey;

let fallos = [];
function comprobar(desc, obtenido, esperado) {
    const ok = obtenido === esperado;
    console.log((ok ? '  OK   ' : '  MAL  ') + desc +
        (ok ? '' : ': esperaba ' + JSON.stringify(esperado) + ' y ha salido ' + JSON.stringify(obtenido)));
    if (!ok) fallos.push(desc);
}

console.log('1. Las teclas del mando de LG se traducen a las que el portal entiende');
comprobar('atras (461) vale como escape', normalizarTecla(461), 27);
comprobar('reproducir (415) vale como OK', normalizarTecla(415), 13);
comprobar('pausa (19) vale como OK', normalizarTecla(19), 13);
comprobar('las flechas no se tocan', normalizarTecla(38), 38);
comprobar('el OK del teclado no se toca', normalizarTecla(13), 13);
comprobar('los numeros no se tocan', normalizarTecla(53), 53);

console.log('2. Los botones de color estan definidos donde se espera');
comprobar('rojo', TECLA_ROJO, 403);
comprobar('verde', TECLA_VERDE, 404);
comprobar('amarillo', TECLA_AMARILLO, 405);
comprobar('azul', TECLA_AZUL, 406);
comprobar('informacion', TECLA_INFO, 457);
comprobar('atras', TECLA_ATRAS, 461);

console.log('3. El puntero encuentra la fila que se ha pulsado');
// Se simula una fila con un par de capas dentro, como las que pinta el portal:
//   <div data-i="4"><div class="info"><div class="name">Canal</div></div></div>
function nodo(atributos, padre) {
    const n = {
        attrs: atributos || {},
        parentNode: padre || null,
        getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    };
    return n;
}
const fila = nodo({ 'data-i': '4' }, global.document.body);
const info = nodo({}, fila);
const nombre = nodo({}, info);

comprobar('pulsando el texto de dentro se encuentra la fila', filaPulsada(nombre), 4);
comprobar('pulsando la propia fila tambien', filaPulsada(fila), 4);
comprobar('pulsando fuera de cualquier fila no devuelve nada', filaPulsada(nodo({}, global.document.body)), -1);

console.log('4. Un clic hace lo mismo que moverse hasta la fila y pulsar OK');
// En una television la convencion del puntero es un solo clic, y es lo que
// prueba el autochequeo de LG. Antes hacian falta dos y eso se leia como que la
// app no responde al puntero.
channels = [{ id: '1', name: 'Uno', cmd: 'http://x' }, { id: '2', name: 'Dos', cmd: 'http://y' }];
view = 'list';
isFullscreen = false;
currentChannel = 0;
let entradas = 0;
goFullscreen = function () { entradas++; };
showChannels = function () {};
startPreview = function () {};

manejarClic({ target: nodo({ 'data-i': '1' }, global.document.body) });
comprobar('el clic mueve la seleccion', currentChannel, 1);
comprobar('y entra a la vez', entradas, 1);

console.log('5. Los atajos hacen lo mismo con los tres mandos');
let hecho = [];
recordCurrent = function () { hecho.push('grabar'); };
toggleFavorite = function () { hecho.push('favorito'); };
toggleFavOnly = function () { hecho.push('solo-favoritos'); };
openRecordings = function () { hecho.push('grabaciones'); };
openGuide = function () { hecho.push('guia'); };
mostrarInfoPrograma = function () { hecho.push('info'); };

function atajo(codigo, vista) {
    view = vista || 'list';
    isFullscreen = false;
    hecho = [];
    atajoGlobal({ keyCode: codigo });
    return hecho[0] || null;
}

// El mismo par de acciones, por el boton de color de LG y por la F de un MAG.
comprobar('rojo de LG graba', atajo(403), 'grabar');
comprobar('F1 del MAG graba igual', atajo(112), 'grabar');
comprobar('verde de LG marca favorito', atajo(404), 'favorito');
comprobar('F4 del MAG marca favorito igual', atajo(115), 'favorito');
comprobar('amarillo de LG filtra favoritos', atajo(405), 'solo-favoritos');
comprobar('F3 del MAG filtra favoritos igual', atajo(114), 'solo-favoritos');
comprobar('F2 del MAG abre grabaciones', atajo(113), 'grabaciones');
comprobar('azul de LG abre la guia', atajo(406), 'guia');
comprobar('el boton de informacion abre la ficha', atajo(457), 'info');

console.log('6. Los atajos se apartan donde estorbarian');
comprobar('en el PIN no se graba nada', atajo(403, 'pin'), null);
comprobar('en el PIN el color verde tampoco hace nada', atajo(404, 'pin'), null);
// En grabaciones, esas teclas borran: no se las puede quedar el atajo global.
comprobar('en grabaciones el rojo no lo intercepta', atajo(403, 'recordings'), null);
comprobar('en grabaciones F1 tampoco', atajo(112, 'recordings'), null);

console.log('7. El teclado del PIN se puede pulsar con el puntero');
pinBuffer = '';
let pintados = 0;
renderPin = function () { pintados++; };
comprobarPin = function () { hecho.push('comprobar-pin'); };
hecho = [];
pinPulsado('1'); pinPulsado('2'); pinPulsado('3'); pinPulsado('4');
comprobar('se componen los digitos', pinBuffer, '1234');
pinPulsado('borrar');
comprobar('la tecla de borrar quita el ultimo', pinBuffer, '123');
pinPulsado('ok');
comprobar('la tecla OK comprueba el PIN', hecho[0], 'comprobar-pin');

console.log('8. La rueda del mando se traduce a las flechas');
let teclas = [];
handleKey = function (e) { teclas.push(e.keyCode); };
manejarRueda({ deltaY: 120, preventDefault() {} });
comprobar('rueda hacia abajo = flecha abajo', teclas[0], 40);
manejarRueda({ deltaY: -120, preventDefault() {} });
comprobar('rueda hacia arriba = flecha arriba', teclas[1], 38);

console.log('9. La guia abierta sobre el video manda ella, no la pantalla completa');
// Dos fallos distintos con la misma raiz:
//
//   - goFullscreen apaga la capa de graficos para dejar ver el video, y
//     openGuide escribia dentro sin volver a encenderla: la guia se pintaba
//     donde no se ve y el boton azul parecia roto.
//   - handleKey miraba isFullscreen ANTES que la vista, asi que con la guia ya
//     abierta las flechas y la rueda seguian cambiando de canal y el boton de
//     atras salia a la miniatura en vez de devolver la imagen.
const capa = elemento('content');
channels = [{ id: '1', name: 'Uno', cmd: 'http://x' }];
currentChannel = 0;
view = 'list';
isFullscreen = true;
capa.style.display = 'none';

openGuideDeVerdad();
comprobar('el azul hace visible la guia', capa.style.display, 'block');
comprobar('queda anotado de donde se vino', guiaDesdeFullscreen, true);

// Con la guia delante, las flechas son suyas.
guide = [{ name: 'A' }, { name: 'B' }, { name: 'C' }];
guideIdx = 0;
view = 'guide';
let canalesCambiados = 0;
let vueltasALaLista = 0;
renderGuide = function () {};
playChannel = function () { canalesCambiados++; };
showChannels = function () { vueltasALaLista++; };

handleKeyDeVerdad({ keyCode: 40 });
comprobar('la flecha abajo baja por la guia', guideIdx, 1);
comprobar('y no cambia de canal', canalesCambiados, 0);

// La rueda pasa por el mismo sitio, asi que hereda el arreglo. La seccion 8
// dejo puesto un doble de handleKey para poder mirar que tecla salia; aqui hace
// falta el de verdad, que es quien decide.
handleKey = handleKeyDeVerdad;
manejarRueda({ deltaY: 120, preventDefault() {} });
comprobar('la rueda tampoco cambia de canal', canalesCambiados, 0);
comprobar('la rueda baja por la guia', guideIdx, 2);

// Y el puntero: pulsar una fila entra en el programa, no saca la barra.
let barras = 0, fichas = 0;
mostrarOsd = function () { barras++; };
abrirFicha = function () { fichas++; };
manejarClic({ target: nodo({ 'data-i': '0' }, global.document.body) });
comprobar('el puntero elige el programa', guideIdx, 0);
comprobar('y no saca la barra del canal', barras, 0);
comprobar('sino que abre la ficha', fichas, 1);

// Atras devuelve el video, no la miniatura.
view = 'guide';
handleKeyDeVerdad({ keyCode: 461 });
comprobar('atras oculta la guia', capa.style.display, 'none');
comprobar('y devuelve el video, no la miniatura', vueltasALaLista, 0);
comprobar('la vista vuelve a ser la del video', view, 'list');
comprobar('sin salir de pantalla completa', isFullscreen, true);

// Desde el menu, en cambio, cerrar la guia si devuelve la lista.
view = 'guide';
isFullscreen = false;
guiaDesdeFullscreen = false;
salirDeGuia();
comprobar('desde el menu si se vuelve a la lista', vueltasALaLista, 1);

// Ver un programa del archivo deja la vista donde toca: si se quedara en
// "guide", las teclas mandarian sobre una guia que ya no esta en pantalla.
view = 'guide';
setViewportFullscreen = function () {};
graficosDelanteInsistiendo = function () {};
esc = esc;
reproducirPantallaCompleta('http://x', 'Canal', 'Programa');
comprobar('al ver el archivo la vista pasa a la del video', view, 'list');

console.log('10. La rueda que manda teclas de pagina mueve en todas las listas');
// El Magic Remote de la tele de pruebas no manda un evento de rueda: manda 33 y
// 34, las teclas de pagina. Solo estaban atendidas a pantalla completa, asi que
// la rueda cambiaba de canal sobre el video y no hacia nada en el listado ni en
// la guia.
handleKey = handleKeyDeVerdad;
// La seccion 9 giro la rueda por el otro camino hace un instante; sin esto el
// guardia contra muescas duplicadas se comeria la primera tecla.
ultimoGiro.camino = ''; ultimoGiro.cuando = 0;
channels = [{ id: '1', name: 'Uno' }, { id: '2', name: 'Dos' }, { id: '3', name: 'Tres' }];
view = 'list';
isFullscreen = false;
currentChannel = 0;
showChannels = function () {};
startPreview = function () {};

handleKey({ keyCode: 34 });
comprobar('pagina abajo baja por el listado', currentChannel, 1);
handleKey({ keyCode: 33 });
comprobar('pagina arriba sube por el listado', currentChannel, 0);

view = 'guide';
guide = [{ name: 'A' }, { name: 'B' }, { name: 'C' }];
guideIdx = 0;
renderGuide = function () {};
handleKey({ keyCode: 34 });
comprobar('y tambien baja por la guia', guideIdx, 1);
handleKey({ keyCode: 33 });
comprobar('y sube por la guia', guideIdx, 0);

// Sobre el video sigue cambiando de canal, que es donde ya funcionaba.
view = 'list';
isFullscreen = true;
currentChannel = 0;
playingChannelIdx = 0;
playChannel = function () {};
mostrarOsd = function () {};
handleKey({ keyCode: 34 });
comprobar('sobre el video sigue cambiando de canal', currentChannel, 1);

// La ficha es la excepcion: ahi 33 y 34 desplazan el texto de cuatro en cuatro.
view = 'ficha';
let saltos = [];
moverFicha = function (n) { saltos.push(n); };
handleKey({ keyCode: 34 });
handleKey({ keyCode: 33 });
comprobar('en la ficha siguen siendo el salto largo', JSON.stringify(saltos),
    JSON.stringify([PASO_FICHA * 4, -PASO_FICHA * 4]));

console.log('11. Un mando que mande las dos cosas no salta de dos en dos');
// No hay Magic Remote original a mano. Si resulta que manda el evento de rueda
// Y la tecla de pagina por la misma muesca, cada giro movería dos posiciones y
// la app se volveria inservible justo con el mando que usa el revisor de LG.
// Asi funciona con las dos clases de mando sin tener que saber cual es.
channels = [{ id: '1' }, { id: '2' }, { id: '3' }, { id: '4' }, { id: '5' }];
view = 'list';
isFullscreen = false;
currentChannel = 0;
ultimoGiro.camino = ''; ultimoGiro.cuando = 0;

// Primera muesca: llegan las dos cosas casi a la vez.
manejarRueda({ deltaY: 120, preventDefault() {} });
handleKey({ keyCode: 34 });
comprobar('una muesca mueve una sola posicion', currentChannel, 1);

// Segunda muesca, 100 ms mas tarde: lo mismo otra vez.
ultimoGiro.cuando -= 100;
manejarRueda({ deltaY: 120, preventDefault() {} });
handleKey({ keyCode: 34 });
comprobar('la muesca siguiente vuelve a mover una', currentChannel, 2);

// Y al que solo manda teclas no se le penaliza por girar rapido: dos muescas
// seguidas por el mismo camino son dos giros de verdad, no un duplicado.
ultimoGiro.camino = 'teclas';
handleKey({ keyCode: 34 });
handleKey({ keyCode: 34 });
comprobar('girar rapido mueve en cada muesca', currentChannel, 4);

console.log('12. Los rotulos de accion se pueden pulsar con el puntero');
// "OK Ver", "◀ Volver", el punto rojo de grabar... tienen pinta de boton, y con
// el Magic Remote se apunta a ellos y se pulsa. Antes no hacian nada: parecian
// botones rotos, que es justo lo que mira el punto 10 del autochequeo de LG.
// Cada rotulo dice de que tecla habla, asi que el clic hace lo que esa tecla.
let teclasEnviadas = [];
handleKey = function (e) { teclasEnviadas.push(e.keyCode); };
view = 'list';
isFullscreen = false;

manejarClic({ target: nodo({ 'data-tecla': '13' }, global.document.body) });
comprobar('pulsar el rotulo OK manda la tecla OK', teclasEnviadas[0], 13);

manejarClic({ target: nodo({ 'data-tecla': '37' }, global.document.body) });
comprobar('pulsar el de volver manda la flecha izquierda', teclasEnviadas[1], 37);

// El punto rojo vive en la barra del canal, o sea a pantalla completa: el
// rotulo se mira antes que la rama del video, si no se lo comeria ella.
isFullscreen = true;
manejarClic({ target: nodo({ 'data-tecla': '403' }, global.document.body) });
comprobar('el punto rojo graba tambien sobre el video', teclasEnviadas[2], 403);

// Y pulsar al lado, donde no hay rotulo, no manda ninguna tecla.
manejarClic({ target: nodo({}, global.document.body) });
comprobar('pulsar fuera de un rotulo no manda nada', teclasEnviadas.length, 3);

console.log('13. Si el video no arranca a la primera, se reintenta');
// Nada mas encender la television su reproductor tarda mas en estar listo que
// la pagina, asi que play() falla. Antes eso se quedaba en un mensaje de
// consola y el usuario veia el menu con la ventana en negro hasta que cambiaba
// de canal a mano. Es lo que mira el punto 3 del autochequeo de LG.
useHTML5 = true;
htmlPlayer = global.__video;
let esperas = [];
global.setTimeout = function (fn, ms) { esperas.push(ms); fn(); return 0; };

global.__video.arranques = 0;
global.__video.fallosPendientes = 0;
arrancarVideo('http://x/uno.m3u8');
comprobar('si arranca a la primera, no se reintenta', global.__video.arranques, 1);

// Ahora que falle dos veces seguidas: debe volver a intentarlo y acabar dentro.
global.__video.arranques = 0;
global.__video.fallosPendientes = 2;
esperas = [];
arrancarVideo('http://x/dos.m3u8');
comprobar('reintenta hasta que entra', global.__video.arranques, 3);
comprobar('separando cada vez mas', JSON.stringify(esperas), JSON.stringify([700, 1500]));

// Y que no reintente para siempre.
global.__video.arranques = 0;
global.__video.fallosPendientes = 99;
esperas = [];
arrancarVideo('http://x/tres.m3u8');
comprobar('se rinde tras cuatro intentos', global.__video.arranques, 4);
comprobar('y no espera mas veces', esperas.length, 3);

// Parar el video cancela lo que quedara en marcha: un reintento que llegue
// tarde no puede resucitar el canal que se acaba de cortar.
global.__video.diferido = true;
global.__video.arranques = 0;
global.__video.fallosPendientes = 1;
global.__pendiente = null;
arrancarVideo('http://x/cuatro.m3u8');
const antes = global.__video.arranques;
pararVideo();
if (global.__pendiente) global.__pendiente();
comprobar('parar el video corta los reintentos', global.__video.arranques, antes);
global.__video.diferido = false;

console.log('');
if (fallos.length) {
    console.log('FALLAN ' + fallos.length + ' comprobaciones:');
    fallos.forEach(f => console.log('  - ' + f));
    process.exit(1);
}
console.log('Las comprobaciones pasan.');
