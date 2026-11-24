<?php
// Lista HLS (.m3u8) de una grabacion de cliente, a partir de su indice
// (indexar_grabaciones.py). Cada linea es un trozo que entrega trozo.php.
//
//   grabacion.php?d=nuevas&f=959_20261124080732.mpg&e=<caduca>&s=<firma>[&desde=600]
//
// La firma la pone el middleware (GRABACIONES_HLS_SECRETO): sin ella no se
// puede pedir una grabacion ajena cambiando el nombre. `desde` (segundos)
// empieza la lista mas adelante: es como avanza la app de Android de antes,
// que no sabe saltar dentro del video.
require __DIR__ . '/comun.php';

list($d, $f, $e, $s) = pedir_grabacion();
$indice = INDICE . $d . '/' . $f . '.json';
if (!is_file($indice)) {
    // Aun sin indice (recien terminada): se hace ahora, son pocos segundos.
    exec('python3 ' . escapeshellarg(INDEXADOR) . ' --una ' . escapeshellarg($d) . ' ' . escapeshellarg($f) . ' 2>&1');
}
$datos = is_file($indice) ? json_decode(file_get_contents($indice), true) : null;
if (!$datos || empty($datos['trozos'])) {
    http_response_code(404);
    exit;
}
$desde = isset($_GET['desde']) && ctype_digit($_GET['desde']) ? (int)$_GET['desde'] : 0;
$base = 'trozo.php?d=' . rawurlencode($d) . '&f=' . rawurlencode($f) . '&e=' . $e . '&s=' . $s;
$lineas = array();
$maximo = 1;
foreach ($datos['trozos'] as $t) {
    if ($t[0] + $t[3] <= $desde) continue;
    $maximo = max($maximo, $t[3]);
    $lineas[] = sprintf('#EXTINF:%.3f,', $t[3]);
    $lineas[] = $base . '&o=' . $t[1] . '&l=' . $t[2];
}
if (!$lineas) {
    http_response_code(404);
    exit;
}
header('Content-Type: application/vnd.apple.mpegurl');
header('Access-Control-Allow-Origin: *');
header('Cache-Control: no-store');
echo "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:" . (int)ceil($maximo) .
     "\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-PLAYLIST-TYPE:VOD\n" . implode("\n", $lineas) . "\n#EXT-X-ENDLIST\n";
