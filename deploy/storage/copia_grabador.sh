#!/bin/bash
# Segundo grabador, controlado por la plataforma nueva, al lado del de Ministra.
#
# En record1 el grabador es una carpeta (/var/www/stalker_portal/storage) con un
# config.php que dice a quien obedece y donde guarda. Esto hace una copia de esa
# carpeta que obedece a la plataforma nueva y guarda en una carpeta suya. El de
# Ministra no se toca: sigue grabando lo suyo exactamente igual.
#
# Ademas deja las grabaciones de las dos plataformas servidas por Apache bajo
# /stalker_portal/quattretv_grab/, que es por donde las pide el deco.
#
# En storage1 se instala en modo archivo (ARCHIVO=1): ahi no se graba nada
# nuevo, la copia solo sirve con su get.php el catchup que ya escribe el de
# Ministra, validando los enlaces con la plataforma nueva. Lee la misma carpeta
# y no escribe en ella.
#
# Uso, en record1 y como root:
#   sudo bash copia_grabador.sh            instala (o rehace) la copia
#   sudo bash copia_grabador.sh --probar   solo dice lo que haria
#   sudo bash copia_grabador.sh --deshacer quita la copia y los enlaces; las
#                                          grabaciones hechas se quedan en disco
#   sudo ARCHIVO=1 bash copia_grabador.sh  en storage1
#
# Volver atras es seguro en cualquier momento: no hay nada compartido con el de
# Ministra salvo el disco y el procesador.
set -euo pipefail

ARCHIVO="${ARCHIVO:-0}"
if [ "$ARCHIVO" = 1 ]; then
    NOMBRE="${NOMBRE:-storage1n}"                    # StorageServer.name en el panel
else
    NOMBRE="${NOMBRE:-record1n}"
fi
API_URL="${API_URL:-https://iptv2.quattre.com/storage_api/}"
PORTAL_URL="${PORTAL_URL:-https://iptv2.quattre.com}"

ORIGEN=/var/www/stalker_portal/storage               # el de Ministra, solo se lee
COPIA=/var/www/stalker_portal/quattretv_storage      # el nuevo
SERVIR=/var/www/stalker_portal/quattretv_grab        # enlaces para reproducir
BASE=$(sed -nE "s/.*define\('RECORDS_DIR', *'([^']+)'.*/\1/p" "$ORIGEN/config.php")
BASE=${BASE%/}                                       # /mnt/record1/quattretv/records
GRABACIONES="$(dirname "$BASE")/records_quattretv"
CASAS="$(dirname "$BASE")/mac_quattretv"
# En modo archivo get.php tiene que leer el archivo de Ministra, que esta en
# <RECORDS_DIR>/archive/<canal>/: la misma carpeta, solo para leer.
[ "$ARCHIVO" = 1 ] && GRABACIONES="$BASE"

MODO=instalar
case "${1:-}" in
    --probar) MODO=probar ;;
    --deshacer) MODO=deshacer ;;
    "") ;;
    *) echo "Uso: $0 [--probar|--deshacer]"; exit 2 ;;
esac

hacer() {
    echo "+ $*"
    [ "$MODO" = probar ] || "$@"
}

[ "$(id -u)" = 0 ] || [ "$MODO" = probar ] || { echo "Hay que lanzarlo con sudo"; exit 1; }
[ -f "$ORIGEN/config.php" ] || { echo "No encuentro $ORIGEN/config.php"; exit 1; }
[ -n "$BASE" ] || { echo "No se pudo leer RECORDS_DIR de $ORIGEN/config.php"; exit 1; }

if [ "$MODO" = deshacer ]; then
    hacer rm -rf "$COPIA" "$SERVIR"
    echo "Quitado. Las grabaciones de la plataforma nueva siguen en $GRABACIONES."
    exit 0
fi

echo "Grabador de Ministra:  $ORIGEN  (graba en $BASE, no se toca)"
if [ "$ARCHIVO" = 1 ]; then
    echo "Copia nueva:           $COPIA  (sirve el archivo de $BASE/archive, solo lee)"
else
    echo "Grabador nuevo:        $COPIA  (graba en $GRABACIONES)"
fi
echo "Obedece a:             $API_URL"

# 1. La copia, sin los dumpstream_* de recambio, sin su cache de tareas ni el
#    volcado de depuracion. Si ya existia se rehace desde el original, asi que
#    lanzar esto otra vez tambien sirve para recoger cambios del de Ministra.
hacer rm -rf "$COPIA"
hacer mkdir -p "$COPIA"
for f in "$ORIGEN"/* "$ORIGEN"/.htaccess; do
    nombre=$(basename "$f")
    case "$nombre" in
        dumpstream_*|data.txt|config.phpBAK|.tasks) continue ;;
    esac
    hacer cp -a "$f" "$COPIA/"
done

# 2. Su configuracion: a quien obedece, como se llama y donde guarda.
hacer sed -i -E \
    -e "s#define\('RECORDS_DIR', *'[^']*'\)#define('RECORDS_DIR', '$GRABACIONES/')#" \
    -e "s#define\('NFS_HOME_PATH', *'[^']*'\)#define('NFS_HOME_PATH', '$CASAS/')#" \
    -e "s#define\('API_URL', *'[^']*'\)#define('API_URL', '$API_URL')#" \
    -e "s#define\('PORTAL_URL', *'[^']*'\)#define('PORTAL_URL', '$PORTAL_URL')#" \
    -e "s#define\('STORAGE_NAME', *'[^']*'\)#define('STORAGE_NAME', '$NOMBRE')#" \
    "$COPIA/config.php"

# 3. Dos rutas que el de Ministra lleva escritas a fuego:
#    - el volcado de depuracion iria a la carpeta del original;
#    - el aviso de "empieza/termina" se manda siempre por http al puerto 80,
#      y la plataforma nueva contesta por https. Se le enseña https y el puerto.
hacer sed -i "s#'/var/www/stalker_portal/storage/data.txt'#__DIR__ . '/../data.txt'#" \
    "$COPIA/Lib/RESTManager.php"
hacer sed -i -E \
    -e "s#conn = httplib\.HTTPConnection\(url\.hostname\)#conn = (httplib.HTTPSConnection if url.scheme == 'https' else httplib.HTTPConnection)(url.hostname, url.port)#" \
    -e "s#conn = http\.client\.HTTPConnection\(url\.hostname\)#conn = (http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection)(url.hostname, url.port)#" \
    "$COPIA/dumpstream"

#    Y lo que mas importa: dumpstream copia todas las pistas (-map 0), y algunos
#    canales (La 1, por ejemplo) llevan pistas de datos con marcas de tiempo
#    rotas. ffmpeg se para al primer segundo ("non monotonically increasing
#    dts"), el reintento choca con el compactador y la grabacion se queda en
#    unos pocos KB. Al de Ministra le pasa igual: de 25 grabaciones de octubre,
#    varias vacias o cortadas. Solo video y audio.
hacer sed -i 's/-sn -map 0 -t/-sn -map 0:v? -map 0:a? -t/g' "$COPIA/dumpstream"

# 4. Sus carpetas. Las del original tienen permisos abiertos y se copian igual.
#    En modo archivo la de grabaciones es la de Ministra y no se toca.
if [ "$ARCHIVO" = 1 ]; then
    hacer mkdir -p "$CASAS"
    hacer chown www-data:www-data "$CASAS"
else
    hacer mkdir -p "$GRABACIONES" "$CASAS"
    hacer chown www-data:www-data "$GRABACIONES" "$CASAS"
    hacer chmod 777 "$GRABACIONES" "$CASAS"
fi
hacer chown -R www-data:www-data "$COPIA"

# 5. Desde donde se reproducen. Dentro de stalker_portal/ porque ahi Apache no
#    lista directorios (-Indexes): en /var/www cualquiera veria la lista.
#    El archivo no hace falta: lo sirve get.php.
if [ "$ARCHIVO" != 1 ]; then
    hacer mkdir -p "$SERVIR"
    hacer ln -sfn "$BASE" "$SERVIR/ministra"
    hacer ln -sfn "$GRABACIONES" "$SERVIR/nuevas"
    hacer chown -h www-data:www-data "$SERVIR" "$SERVIR/ministra" "$SERVIR/nuevas"
fi

[ "$MODO" = probar ] && { echo "(simulacro: no se ha cambiado nada)"; exit 0; }

# 6. Comprobaciones. Ninguna graba nada.
echo
grep -E "define\('(STORAGE_NAME|RECORDS_DIR|API_URL|PORTAL_URL)'" "$COPIA/config.php"
grep -q "HTTPSConnection" "$COPIA/dumpstream" || { echo "ERROR: no se pudo parchear el aviso de dumpstream"; exit 1; }
grep -q -- "-map 0:v? -map 0:a?" "$COPIA/dumpstream" || { echo "ERROR: no se pudo parchear las pistas de dumpstream"; exit 1; }
diff -q "$ORIGEN/config.php" "$COPIA/config.php" >/dev/null && { echo "ERROR: la copia sigue igual que el original"; exit 1; }
respuesta=$(curl -s -m 5 "http://127.0.0.1:88/stalker_portal/quattretv_storage/rest.php" || true)
echo "rest.php del nuevo contesta: ${respuesta:0:120}"
curl -s -o /dev/null -m 5 -w "Plataforma nueva: %{http_code}\n" "${PORTAL_URL%/}/health" || true
echo
echo "Listo. Grabador '$NOMBRE' instalado; en el panel se da de alta con"
echo "  manage.py preparar_grabadores"
