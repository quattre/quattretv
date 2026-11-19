#!/bin/bash
# Trae a iptv2 los ajustes del WebGrab de la maquina de Ministra y deja listo
# el nuevo (5.6, .NET 9) en ~/wg++ de quattre, sin sudo. Se lanza desde el PC
# de la oficina (que entra por clave en las dos maquinas):
#   bash deploy/iptv2/webgrab_traer.sh
# No toca nada en la maquina de Ministra (solo lee) ni programa nada en iptv2.
set -euo pipefail
VIEJA="ssh -p 2101 quattre@185.25.27.50"
NUEVA="ssh -p 12121 quattre@185.25.27.51"

# 1. Ajustes (llevan la licencia) y las definiciones de las 4 webs que se usan.
$VIEJA 'cd /home/quattre/wg++ && tar czf - WebGrab++.config.xml rex/rex.config.xml mdb/mdb.config.xml \
    siteini.pack/Spain/orange.es.ini siteini.pack/Spain/elpais.com.E.ini \
    siteini.pack/Spain/m.movistarplus.es.ini siteini.pack/Spain/elmundo.es.ini' \
  | $NUEVA 'mkdir -p ~/wgnuevo/viejo && tar xzf - -C ~/wgnuevo/viejo && chmod -R go-rwx ~/wgnuevo/viejo'

# 2. .NET 9 (solo el runtime) en ~/.dotnet y el WebGrab nuevo en ~/wg++.
$NUEVA 'set -e
cd ~/wgnuevo
[ -x ~/.dotnet/dotnet ] || { curl -sL -o dotnet-install.sh https://dot.net/v1/dotnet-install.sh; bash dotnet-install.sh --channel 9.0 --runtime dotnet --install-dir ~/.dotnet | tail -2; }
~/.dotnet/dotnet --list-runtimes
[ -d .wg++ ] || tar xzf wg.tar.gz
mkdir -p ~/wg++ && cp -a .wg++/bin.net ~/wg++/ && mkdir -p ~/wg++/siteini.user ~/wg++/rex ~/wg++/mdb
cp viejo/WebGrab++.config.xml ~/wg++/ && cp viejo/siteini.pack/Spain/*.ini ~/wg++/siteini.user/
cp viejo/rex/rex.config.xml ~/wg++/rex/ && cp viejo/mdb/mdb.config.xml ~/wg++/mdb/
chmod 600 ~/wg++/WebGrab++.config.xml
ls -la ~/wg++ ~/wg++/siteini.user
echo LISTO'
