<?php
// Lo comun a grabacion.php y trozo.php. No saca nada si se pide directamente.
define('INDICE', '/mnt/record1/quattretv/grab_hls/indice/');
define('INDEXADOR', '/home/quattre/archivo/indexar_grabaciones.py');
$CARPETAS = array(
    'nuevas' => '/mnt/record1/quattretv/records_quattretv/',
    'ministra' => '/mnt/record1/quattretv/records/',
);

// (carpeta, fichero, caducidad, firma) de la peticion, o 403/400 y fuera.
function pedir_grabacion() {
    global $CARPETAS;
    $d = isset($_GET['d']) ? $_GET['d'] : '';
    $f = isset($_GET['f']) ? $_GET['f'] : '';
    $e = isset($_GET['e']) ? $_GET['e'] : '';
    $s = isset($_GET['s']) ? $_GET['s'] : '';
    if (!isset($CARPETAS[$d]) || !preg_match('/^\d+_\d{14}\.(mpg|ts)$/', $f) || !ctype_digit($e)) {
        http_response_code(400);
        exit;
    }
    // El secreto no esta en el repositorio: lo deja grabaciones_hls.sh.
    $secreto = @include __DIR__ . '/secreto.php';
    if (!$secreto || (int)$e < time()
            || !hash_equals(substr(hash_hmac('sha256', $d . '/' . $f . '/' . $e, $secreto), 0, 32), $s)) {
        http_response_code(403);
        exit;
    }
    return array($d, $f, $e, $s);
}
