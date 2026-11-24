<?php
// Un trozo de una grabacion de cliente, tal cual: los bytes de `o` a `o + l`
// del fichero. Es lo que pide el reproductor por cada linea de la lista que
// da grabacion.php, con la misma firma. Solo lee: nunca escribe ni borra.
//
//   trozo.php?d=nuevas&f=959_20261124080732.mpg&e=..&s=..&o=123456&l=7654321
require __DIR__ . '/comun.php';

list($d, $f) = pedir_grabacion();
$o = isset($_GET['o']) ? $_GET['o'] : '';
$l = isset($_GET['l']) ? $_GET['l'] : '';
if (!ctype_digit($o) || !ctype_digit($l) || $l == 0 || $l > (64 << 20)) {
    http_response_code(400);
    exit;
}
$ruta = $CARPETAS[$d] . $f;
$o = (int)$o;
$l = (int)$l;
$tam = @filesize($ruta);
if ($tam === false || $o >= $tam) {
    http_response_code(404);
    exit;
}
$l = min($l, $tam - $o);

// Algun reproductor pide el trozo por partes (Range), dentro de el.
$desde = 0;
$hasta = $l - 1;
if (isset($_SERVER['HTTP_RANGE']) && preg_match('/^bytes=(\d*)-(\d*)$/', $_SERVER['HTTP_RANGE'], $m)) {
    if ($m[1] !== '') {
        $desde = (int)$m[1];
        if ($m[2] !== '') $hasta = min((int)$m[2], $l - 1);
    } elseif ($m[2] !== '') {
        $desde = max(0, $l - (int)$m[2]);
    }
    if ($desde > $hasta) {
        http_response_code(416);
        header('Content-Range: bytes */' . $l);
        exit;
    }
    http_response_code(206);
    header('Content-Range: bytes ' . $desde . '-' . $hasta . '/' . $l);
}
$fp = fopen($ruta, 'rb');
if (!$fp) {
    http_response_code(404);
    exit;
}
header('Content-Type: video/mp2t');
header('Content-Length: ' . ($hasta - $desde + 1));
header('Accept-Ranges: bytes');
header('Access-Control-Allow-Origin: *');
// Una grabacion terminada no cambia: el aparato lo puede guardar.
header('Cache-Control: private, max-age=86400');
if ($_SERVER['REQUEST_METHOD'] === 'HEAD') exit;
set_time_limit(0);
while (ob_get_level()) ob_end_flush();
fseek($fp, $o + $desde);
$quedan = $hasta - $desde + 1;
while ($quedan > 0 && !feof($fp) && !connection_aborted()) {
    $bloque = fread($fp, min(1 << 20, $quedan));
    if ($bloque === false || $bloque === '') break;
    echo $bloque;
    flush();
    $quedan -= strlen($bloque);
}
fclose($fp);
