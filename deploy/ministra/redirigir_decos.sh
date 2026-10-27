#!/bin/bash
# Pasa decos concretos de Ministra a la plataforma nueva sin tocar el deco.
#
# Todos los MAG piden http://iptv1.quattre.com/stalker_portal/... y mandan su
# MAC en la cookie "mac" en cada peticion. El nginx de la maquina de Ministra
# mira esa cookie: si la MAC esta en la lista, la peticion se la pasa a
# https://iptv2.quattre.com; si no, a Ministra, como siempre. Un deco se pasa
# o se devuelve cambiando una linea de la lista; ni el deco ni Ministra se
# enteran.
#
# Antes de pasar un deco hay que copiar su cuenta a la plataforma nueva
# (manage.py importar_ministra --mac ...), o se encontrara la pantalla de acceso.
#
# Uso, en la maquina de Ministra (puerto 2101) y con sudo:
#   sudo bash redirigir_decos.sh --instalar           prepara nginx (una vez)
#   sudo bash redirigir_decos.sh --pasar MAC [MAC..]  esos decos van a la nueva
#   sudo bash redirigir_decos.sh --devolver MAC [..]  vuelven a Ministra
#   sudo bash redirigir_decos.sh --lista              quien esta pasado
#   sudo bash redirigir_decos.sh --deshacer           todo como estaba
set -euo pipefail

# sites-enabled/default es un enlace: se trabaja sobre el fichero de verdad, y
# la copia va FUERA de sites-enabled, porque nginx carga todo lo que hay ahi y
# una copia del servidor dentro lo duplicaria.
SITIO=$(readlink -f "${SITIO:-/etc/nginx/sites-enabled/default}")
NGINX_DIR="${NGINX_DIR:-/etc/nginx}"
MAPA="$NGINX_DIR/conf.d/quattretv_decos.conf"
LISTA="$NGINX_DIR/quattretv_decos.map"
DESTINO=iptv2.quattre.com
COPIA="$NGINX_DIR/quattretv-default.antes"

[ "$(id -u)" = 0 ] || [ -n "${PRUEBA:-}" ] || { echo "Hay que lanzarlo con sudo"; exit 1; }
# Solo para probarlo fuera de la maquina: con que se comprueba y se recarga.
RECARGAR="${RECARGAR:-systemctl reload nginx}"
COMPROBAR="${COMPROBAR:-nginx -t}"

normalizar() {   # 00:1a:79:4b:56:7e -> 00:1A:79:4B:56:7E, o vacio si no es una MAC
    local m
    m=$(echo "$1" | tr -d ' ' | tr '[:lower:]' '[:upper:]' | sed 's/%3A/:/g; s/[-.]/:/g')
    [[ "$m" =~ ^([0-9A-F]{2}:){5}[0-9A-F]{2}$ ]] && echo "$m"
}

regex_de() {     # la cookie llega con los dos puntos tal cual o como %3A, y en
                 # cualquier mezcla de mayusculas: se aceptan todas
    echo "$1" | sed 's/:/(:|%3[aA])/g'
}

recargar() {
    if $COMPROBAR 2>/tmp/quattretv_nginx_t; then
        $RECARGAR
        echo "nginx recargado."
    else
        cat /tmp/quattretv_nginx_t
        echo "ERROR: nginx no acepta la configuracion; no se ha recargado."
        return 1
    fi
}

reescribir_lista() {   # $@ = MACs normalizadas
    {
        echo "# Decos que van a la plataforma nueva. Lo escribe redirigir_decos.sh."
        for m in "$@"; do
            echo "~*^$(regex_de "$m")\$ 1;  # $m"
        done
    } > "$LISTA.nuevo"
    mv "$LISTA.nuevo" "$LISTA"
}

macs_actuales() {
    [ -f "$LISTA" ] && grep -o '# [0-9A-F:]\{17\}$' "$LISTA" | cut -c3- || true
}

case "${1:-}" in
--instalar)
    grep -q "__quattretv_nueva" "$SITIO" && { echo "Ya estaba instalado."; exit 0; }
    cp "$SITIO" "$COPIA"
    [ -f "$LISTA" ] || reescribir_lista
    cat > "$MAPA" <<MAPA
# Que decos se pasan a la plataforma nueva (ver redirigir_decos.sh).
map \$cookie_mac \$quattretv_nueva {
    default 0;
    include quattretv_decos.map;   # relativo a /etc/nginx
}
MAPA
    # Dentro de "location /": si la MAC esta en la lista, la peticion se desvia
    # a una location interna que habla con la nueva. Las demas no cambian.
    python3 - "$SITIO" <<'PY'
import sys, re
ruta = sys.argv[1]
texto = open(ruta).read()
desvio = (
    "        if ($quattretv_nueva) { rewrite ^ /__quattretv_nueva$uri last; }\n"
)
nueva = """
    # Decos pasados a la plataforma nueva (redirigir_decos.sh).
    location ^~ /__quattretv_nueva/ {
        internal;
        rewrite ^/__quattretv_nueva(/.*)$ $1 break;
        proxy_pass https://DESTINO;
        proxy_set_header Host DESTINO;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_ssl_server_name on;
        proxy_read_timeout 60s;
    }
""".replace("DESTINO", "iptv2.quattre.com")
# El desvio tiene que ir en todas las location que atienden al deco: la
# general y la de ficheros estaticos, que si no serviria el CSS de Ministra.
cuenta = 0
def meter(m):
    global cuenta
    cuenta += 1
    return m.group(0) + "\n" + desvio
texto = re.sub(r"location\s+/\s*\{", meter, texto, count=1)
texto = re.sub(r"location\s+~\*\s+\\\.\(htm\|jpeg\|gif\|css\)\$\s*\{", meter, texto, count=1)
if cuenta == 0:
    sys.exit("No encuentro 'location /' en " + ruta)
pos = texto.rindex("}")
texto = texto[:pos] + nueva + texto[pos:]
open(ruta, "w").write(texto)
PY
    if ! recargar; then
        cp "$COPIA" "$SITIO"; rm -f "$MAPA"
        echo "Devuelto a como estaba."; exit 1
    fi
    echo "Instalado. Ningun deco esta pasado todavia: usa --pasar MAC."
    ;;
--pasar|--devolver)
    accion=$1; shift
    [ $# -gt 0 ] || { echo "Falta la MAC"; exit 2; }
    grep -q "__quattretv_nueva" "$SITIO" || { echo "Primero --instalar"; exit 1; }
    mapfile -t actuales < <(macs_actuales)
    for m in "$@"; do
        n=$(normalizar "$m") || true
        [ -n "$n" ] || { echo "No es una MAC: $m"; exit 2; }
        if [ "$accion" = --pasar ]; then
            printf '%s\n' "${actuales[@]}" | grep -qx "$n" || actuales+=("$n")
            echo "  $n -> plataforma nueva"
        else
            mapfile -t actuales < <(printf '%s\n' "${actuales[@]}" | grep -vx "$n" || true)
            echo "  $n -> Ministra"
        fi
    done
    cp -a "$LISTA" "$LISTA.antes"
    reescribir_lista $(printf '%s\n' "${actuales[@]}" | grep . || true)
    recargar || { cp -a "$LISTA.antes" "$LISTA"; exit 1; }
    echo "Decos en la plataforma nueva: $(macs_actuales | grep -c . || true)"
    ;;
--lista)
    macs_actuales
    ;;
--deshacer)
    [ -f "$COPIA" ] && cp "$COPIA" "$SITIO"
    rm -f "$MAPA"
    recargar
    echo "Todo como estaba. La lista se queda en $LISTA por si se quiere volver."
    ;;
*)
    sed -n '2,21p' "$0"; exit 2 ;;
esac
