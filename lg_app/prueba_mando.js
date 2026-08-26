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

console.log('');
if (fallos.length) {
    console.log('FALLAN ' + fallos.length + ' comprobaciones:');
    fallos.forEach(f => console.log('  - ' + f));
    process.exit(1);
}
console.log('Las comprobaciones pasan.');
