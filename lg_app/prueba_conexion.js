// Banco de pruebas: se simula la tele (documento, almacenamiento, XHR) y se
// comprueba el comportamiento real de la logica de conexion de la app.
const fs = require('fs');
const html = fs.readFileSync('/home/sergio/quattretv/.claude/worktrees/epg-grabaciones/lg_app/index.html','utf8');
const codigo = /<script[^>]*>([\s\S]*?)<\/script>/.exec(html)[1];

let escenario = {};      // url -> 'ok' | 'error' | 'silencio'
let respuestaPortal = null;
let navegado = null;
let textos = [];
let temporizadores = [];

global.localStorage = { d:{}, getItem(k){return this.d[k]||null;}, setItem(k,v){this.d[k]=v;} };
global.document = { getElementById: () => ({
    set className(v){}, get className(){return '';},
    set textContent(v){ textos.push(v); },
    focus(){}, onclick:null, onkeydown:null }) };
global.window = { addEventListener(){}, location:{ set href(v){ navegado = v; } } };
global.setTimeout = (fn, ms) => { const id = temporizadores.length; temporizadores.push({fn, ms}); return id; };
global.clearTimeout = (id) => { if (temporizadores[id]) temporizadores[id] = null; };

global.XMLHttpRequest = function(){
    this.open = function(m, url){ this.url = url; };
    this.send = function(){
        const base = this.url.split('/ping')[0];
        const modo = escenario[base] || 'silencio';
        if (modo === 'silencio') return;              // no contesta: vence el plazo
        this.readyState = 4;
        this.status = modo === 'ok' ? 200 : 502;
        this.responseText = respuestaPortal ? JSON.stringify({ok:true, portal:respuestaPortal}) : '{"ok":true}';
        this.onreadystatechange();
    };
    this.abort = function(){};
};
// document.getElementById devuelve objetos nuevos; se captura el texto arriba
eval(codigo.replace('window.onload = function () {', 'global.arrancar = function () {').replace(/};\s*$/, '};'));

function vencerPlazos(){
    for (let i = 0; i < temporizadores.length; i++) {
        const t = temporizadores[i];
        if (t && t.ms === 8000) { temporizadores[i] = null; t.fn(); }
    }
}
function reset(){ navegado=null; textos=[]; temporizadores=[]; localStorage.d={}; respuestaPortal=null; }
let fallos = 0;
function comprobar(nombre, cond, extra){
    console.log((cond ? '  OK   ' : ' FALLO ') + nombre + (extra!==undefined ? ' -> '+extra : ''));
    if (!cond) fallos++;
}

console.log('\n== 1. El primero contesta ==');
reset(); escenario = {'https://iptv2.quattre.com':'ok','https://iptv1.quattre.com':'ok'};
arrancar();
comprobar('entra por iptv2', navegado === 'https://iptv2.quattre.com/quattretv/stb/', navegado);
comprobar('recuerda cual funciono', localStorage.d.ultimo_servidor === 'https://iptv2.quattre.com');

console.log('\n== 2. El primero no contesta, el segundo si ==');
reset(); escenario = {'https://iptv2.quattre.com':'silencio','https://iptv1.quattre.com':'ok'};
arrancar(); vencerPlazos();
comprobar('cae al segundo', navegado === 'https://iptv1.quattre.com/quattretv/stb/', navegado);

console.log('\n== 3. Empieza por el que funciono la ultima vez ==');
reset(); localStorage.d.ultimo_servidor = 'https://iptv1.quattre.com';
escenario = {'https://iptv2.quattre.com':'ok','https://iptv1.quattre.com':'ok'};
arrancar();
comprobar('prueba primero el recordado', navegado === 'https://iptv1.quattre.com/quattretv/stb/', navegado);

console.log('\n== 4. Ninguno contesta: reintenta solo ==');
reset(); escenario = {'https://iptv2.quattre.com':'silencio','https://iptv1.quattre.com':'silencio'};
arrancar(); vencerPlazos();
const pendientes = temporizadores.filter(t => t && t.ms !== 8000);
comprobar('programa un reintento', pendientes.length >= 1, pendientes.map(t=>t.ms+'ms').join(','));
comprobar('la primera espera es de 2 s', pendientes.some(t => t.ms === 2000));
comprobar('avisa de que reintenta', textos.some(t => /Reintentando en/.test(t)));
comprobar('no navega a ningun sitio roto', navegado === null, navegado);

console.log('\n== 5. El servidor manda a otro portal ==');
reset(); escenario = {'https://iptv2.quattre.com':'ok'}; respuestaPortal = 'https://otro.quattre.com/tv/';
arrancar();
comprobar('hace caso al servidor', navegado === 'https://otro.quattre.com/tv/', navegado);

console.log('\n' + (fallos ? 'FALLOS: '+fallos : 'TODO CORRECTO'));
process.exit(fallos ? 1 : 0);
