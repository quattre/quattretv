<?php
// Un trozo de una pieza del archivo de siempre, tal cual: los bytes de `o` a
// `o + l` de records/archive/<c>/<f>. Es lo que pide el reproductor por cada
// linea de la lista .m3u8 que monta el middleware (ver rangos.php).
//
//   trozo.php?c=2&f=20261124-09.mpg&o=123456&l=7654321
//
// Solo lee: nunca escribe ni borra nada del archivo.
$ARCHIVO = '/mnt/storage1/quattretv/records/archive/';

$c = isset($_GET['c']) ? $_GET['c'] : '';
$f = isset($_GET['f']) ? $_GET['f'] : '';
$o = isset($_GET['o']) ? $_GET['o'] : '';
$l = isset($_GET['l']) ? $_GET['l'] : '';
if (!preg_match('/^\d{1,6}$/', $c) || !preg_match('/^\d{8}-\d{2}\.mpg(-temp)?$/', $f)
        || !ctype_digit($o) || !ctype_digit($l) || $l == 0 || $l > (64 << 20)) {
    http_response_code(400);
    exit;
}
$ruta = $ARCHIVO . $c . '/' . $f;
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
// Lo ya grabado no cambia: el aparato lo puede guardar.
header('Cache-Control: public, max-age=86400');
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
