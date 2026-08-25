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

console.log('4. Un clic en la lista selecciona, y el segundo entra');
channels = [{ id: '1', name: 'Uno', cmd: 'http://x' }, { id: '2', name: 'Dos', cmd: 'http://y' }];
view = 'list';
isFullscreen = false;
currentChannel = 0;
let entradas = 0;
goFullscreen = function () { entradas++; };
showChannels = function () {};
startPreview = function () {};

manejarClic({ target: nodo({ 'data-i': '1' }, global.document.body) });
comprobar('el primer clic mueve la seleccion', currentChannel, 1);
comprobar('y no entra todavia', entradas, 0);

manejarClic({ target: nodo({ 'data-i': '1' }, global.document.body) });
comprobar('el segundo clic sobre lo mismo entra', entradas, 1);

console.log('');
if (fallos.length) {
    console.log('FALLAN ' + fallos.length + ' comprobaciones:');
    fallos.forEach(f => console.log('  - ' + f));
    process.exit(1);
}
console.log('Las comprobaciones pasan.');
