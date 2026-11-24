<?php
// Trozos del archivo de siempre (piezas horarias de dumpstream) entre dos
// instantes, del indice que escribe indexar_archivo.py. Para el middleware,
// que monta con ellos la lista .m3u8 de un programa.
//
//   rangos.php?c=2&desde=1763971200&hasta=1763974800   (segundos UTC)
//
// Devuelve las piezas en orden, cada una con sus trozos:
//   [{"f": "20261124-09.mpg", "t": [[inicio, posicion, longitud, duracion, pts], ...]}, ...]
header('Content-Type: application/json');
header('Cache-Control: no-store');
date_default_timezone_set('Europe/Madrid');   // las piezas se llaman por la hora de aqui

$c = isset($_GET['c']) ? $_GET['c'] : '';
$desde = isset($_GET['desde']) ? $_GET['desde'] : '';
$hasta = isset($_GET['hasta']) ? $_GET['hasta'] : '';
if (!preg_match('/^\d{1,6}$/', $c) || !ctype_digit($desde) || !ctype_digit($hasta)
        || $hasta < $desde || $hasta - $desde > 12 * 3600) {
    http_response_code(400);
    echo '[]';
    exit;
}
$desde = (int)$desde;
$hasta = (int)$hasta;
$dir = __DIR__ . '/indice/' . $c . '/';
$piezas = array();
$vistas = array();
// Una pieza empieza en su hora (o despues, si el grabador se corto), asi que
// basta con mirar desde la hora anterior a `desde`.
for ($h = intdiv($desde - 3600, 3600) * 3600; $h <= $hasta; $h += 3600) {
    $nombre = date('Ymd-H', $h);
    foreach (array($nombre . '.mpg-temp', $nombre . '.mpg') as $f) {
        if (isset($vistas[$f]) || !is_file($dir . $f . '.json')) continue;
        $vistas[$f] = true;
        $datos = json_decode(file_get_contents($dir . $f . '.json'), true);
        if (!$datos || empty($datos['trozos'])) continue;
        $dentro = array();
        foreach ($datos['trozos'] as $t) {
            if ($t[0] + $t[3] > $desde && $t[0] < $hasta) $dentro[] = $t;
        }
        if ($dentro) $piezas[] = array('f' => $f, 'inicio' => $datos['trozos'][0][0], 't' => $dentro);
    }
}
usort($piezas, function ($a, $b) { return $a['inicio'] < $b['inicio'] ? -1 : 1; });
echo json_encode($piezas);
