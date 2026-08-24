// Banco de pruebas de la reconexion DEL PORTAL (templates/stb/portal.html),
// no de la app. Son dos cosas distintas: el lanzador resuelve el arranque sin
// red — eso lo prueba prueba_conexion.js — y esto resuelve perder la red
// estando ya dentro viendo la television.
//
// Se simula la tele (documento, XHR, temporizadores, navigator) y se comprueba
// el comportamiento de verdad, no que el codigo "parezca" correcto.
//
//   node lg_app/prueba_portal_sin_red.js
const fs = require('fs');
const RUTA = __dirname + '/../templates/stb/portal.html';
const html = fs.readFileSync(RUTA, 'utf8');
const codigo = /<script[^>]*>([\s\S]*?)<\/script>/.exec(html)[1];

// ---------- la tele de mentira ----------
let elementos = {};
let temporizadores = [];
let oyentes = {};
let modoServidor = 'ok';     // 'ok' | 'silencio' | 'error500' | 'sinruta'
let peticiones = [];

function elemento(id) {
    if (!elementos[id]) {
        elementos[id] = { id, style: { display: 'none' }, innerHTML: '',
                          className: '', textContent: '' };
    }
    return elementos[id];
}

global.document = {
    getElementById: elemento,
    body: { style: {} },
    onkeydown: null,
};
global.window = {
    addEventListener(ev, fn) { (oyentes[ev] = oyentes[ev] || []).push(fn); },
    onresize: null, onload: null,
};
global.navigator = { onLine: true };
global.console = console;
global.setTimeout = (fn, ms) => { temporizadores.push({ fn, ms, vivo: true }); return temporizadores.length - 1; };
global.clearTimeout = (id) => { if (temporizadores[id]) temporizadores[id].vivo = false; };
global.setInterval = () => 0;
global.clearInterval = () => {};

global.XMLHttpRequest = function () {
    const yo = this;
    this.open = function (m, url) { yo.url = url; };
    this.abort = function () {};
    this.send = function () {
        peticiones.push(yo.url);
        if (modoServidor === 'silencio') return;          // no contesta nunca
        yo.readyState = 4;
        if (modoServidor === 'sinruta') { yo.status = 0; yo.responseText = ''; }
        else if (modoServidor === 'error500') { yo.status = 500; yo.responseText = ''; }
        else { yo.status = 200; yo.responseText = JSON.stringify({ js: { result: true } }); }
        yo.onreadystatechange();
    };
};

eval(codigo);

// ---------- utilidades ----------
function vencerPlazo(ms) {
    // Dispara el temporizador vivo mas antiguo con esa duracion.
    for (let i = 0; i < temporizadores.length; i++) {
        const t = temporizadores[i];
        if (t && t.vivo && t.ms === ms) { t.vivo = false; t.fn(); return true; }
    }
    return false;
}
function avisoVisible() { return elemento('sinred').style.display === 'block'; }
function textoAviso() { return elemento('sinred-detalle').innerHTML; }
function reset() {
    elementos = {}; temporizadores = []; peticiones = [];
    modoServidor = 'ok'; navigator.onLine = true;
    hayRed = true; vueltaRed = 0;
}

let fallos = [];
function comprobar(desc, obtenido, esperado) {
    const ok = obtenido === esperado;
    console.log((ok ? '  OK   ' : '  MAL  ') + desc +
                (ok ? '' : ': esperaba ' + JSON.stringify(esperado) +
                           ' y ha salido ' + JSON.stringify(obtenido)));
    if (!ok) fallos.push(desc);
}

// ---------- las pruebas ----------

console.log('1. Una peticion que no contesta nunca');
reset();
modoServidor = 'silencio';
api('type=itv&action=get_ordered_list&p=0', function () {});
comprobar('todavia no se avisa (la peticion sigue en curso)', avisoVisible(), false);
vencerPlazo(12000);                       // vence el plazo de la peticion
comprobar('sale el aviso de conexion perdida', avisoVisible(), true);
comprobar('dice cuanto falta para reintentar', /Reintentando en 2 s/.test(textoAviso()), true);

console.log('2. El reintento tambien falla: la espera crece');
vencerPlazo(2000);                        // toca reintentar
comprobar('se ha reintentado', peticiones.length >= 2, true);
vencerPlazo(12000);                       // ese reintento tampoco contesta
comprobar('sigue el aviso', avisoVisible(), true);
comprobar('ahora espera 4 s', /Reintentando en 4 s/.test(textoAviso()), true);

console.log('3. Vuelve la red');
modoServidor = 'ok';
vencerPlazo(4000);
comprobar('se quita el aviso', avisoVisible(), false);
comprobar('se da la red por recuperada', hayRed, true);

console.log('4. Un error 500 del servidor NO es falta de red');
reset();
modoServidor = 'error500';
api('type=itv&action=get_ordered_list&p=0', function () {});
comprobar('no se avisa de falta de red', avisoVisible(), false);
comprobar('la red se sigue dando por buena', hayRed, true);

console.log('5. No llegar al servidor (status 0) SI lo es');
reset();
modoServidor = 'sinruta';
api('type=itv&action=get_ordered_list&p=0', function () {});
comprobar('sale el aviso', avisoVisible(), true);

console.log('6. La tele avisa de que ha vuelto la red: no se espera al reintento');
reset();
modoServidor = 'sinruta';
api('type=itv&action=get_ordered_list&p=0', function () {});
comprobar('estamos avisando', avisoVisible(), true);
const antes = peticiones.length;
modoServidor = 'ok';
oyentes['online'].forEach(function (fn) { fn(); });
comprobar('se prueba en el acto, sin esperar', peticiones.length > antes, true);
comprobar('y se recupera', avisoVisible(), false);

console.log('7. La tele avisa de que se ha ido la red');
reset();
oyentes['offline'].forEach(function (fn) { fn(); });
comprobar('sale el aviso sin esperar a que falle una peticion', avisoVisible(), true);

console.log('8. El error del reproductor con la red caida no miente');
reset();
hayRed = false;
navigator.onLine = false;
useHTML5 = true;
htmlPlayer = { onerror: null };
// se vuelve a montar el manejador tal y como lo hace init()
htmlPlayer.onerror = function () {
    var sinRed = !hayRed || (typeof navigator !== 'undefined' && navigator.onLine === false);
    if (sinRed) { seCayoLaRed(); return; }
    toast('Este contenido no se puede reproducir en este dispositivo');
};
hayRed = true;               // que seCayoLaRed no salga por la guarda
navigator.onLine = false;
htmlPlayer.onerror();
comprobar('avisa de la red, no del formato', avisoVisible(), true);
comprobar('no dice que el aparato no puede con el formato',
          /no se puede reproducir/i.test(elemento('toast').innerHTML), false);

console.log('');
if (fallos.length) {
    console.log('FALLAN ' + fallos.length + ' comprobaciones:');
    fallos.forEach(function (f) { console.log('  - ' + f); });
    process.exit(1);
}
console.log('Las comprobaciones pasan.');
