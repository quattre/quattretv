<?php
// Ministra deja de archivar unos canales (para que los archive la plataforma
// nueva, ver apps/pvr/management/commands/pasar_archivo.py). Hace lo mismo que
// quitar el archivo de un canal en el panel de Ministra: borra su tarea de la
// tabla tv_archive y manda parar su grabador en storage1. Los ficheros
// grabados no se tocan.
//
//   php quitar_archivo.php 88 43          quita (id internos de Ministra)
//   php quitar_archivo.php --ver 88 43    solo dice lo que hay
//   php quitar_archivo.php --poner 88 43  lo devuelve a Ministra (storage1)
$_SERVER['TARGET'] = 'ADM';              // como las tareas de Ministra (server/tasks)
chdir('/var/www/stalker_portal/server');
require_once '/var/www/stalker_portal/server/common.php';

$args = array_slice($argv, 1);
$modo = 'quitar';
if ($args && $args[0] === '--ver') { $modo = 'ver'; array_shift($args); }
if ($args && $args[0] === '--poner') { $modo = 'poner'; array_shift($args); }
if (!$args) { fwrite(STDERR, "Faltan los id de canal\n"); exit(2); }

$archivo = new \Ministra\Lib\TvArchive();
foreach ($args as $id) {
    $id = (int) $id;
    $tareas = $archivo->getAllTasksForChannel($id);
    $donde = implode(',', array_map(function ($t) { return $t['storage_name']; }, $tareas));
    if ($modo === 'ver') {
        echo "$id: " . ($donde ?: 'sin tarea') . "\n";
    } elseif ($modo === 'poner') {
        echo "$id: " . var_export($archivo->createTask($id, 'storage1'), true) . "\n";
    } elseif (!$tareas) {
        echo "$id: ya no tenia tarea\n";
    } else {
        echo "$id: estaba en $donde; quitado: " . var_export($archivo->deleteTask($id), true) . "\n";
    }
}
