# Vhost para la plataforma nueva, en el nginx que YA tiene el puerto 80
# (la maquina 192.168.100.10, la de Ministra).
#
# Con esto la plataforma nueva se sirve en http://iptv2.quattre.com/ sin puerto
# raro y sin tocar el router. Y el cambio definitivo pasa a ser una linea: en el
# vhost de iptv1 se cambia el proxy_pass y se recarga nginx, con vuelta atras
# inmediata.
#
# OJO CON EL NOMBRE DEL FICHERO. nginx incluye primero conf.d/*.conf y luego
# sites-enabled/*, y el primer server{} de un puerto es el "default" que atiende
# todo lo que no case por nombre. El bloque que ya existe se llama "default", asi
# que este fichero TIENE que ordenarse despues alfabeticamente (por eso el "zz-")
# y estar en sites-enabled. Si se metiera en conf.d cogeria el papel de default y
# se llevaria TODO el trafico de iptv1 a la plataforma nueva.
#
#   sudo cp zz-iptv2.quattre.com /etc/nginx/sites-available/
#   sudo ln -s /etc/nginx/sites-available/zz-iptv2.quattre.com /etc/nginx/sites-enabled/
#   sudo nginx -t && sudo systemctl reload nginx
#
# Comprobacion de que no se ha tocado lo de siempre:
#   curl -I -H 'Host: iptv1.quattre.com' http://127.0.0.1/   -> Ministra
#   curl -I -H 'Host: iptv2.quattre.com' http://127.0.0.1/   -> gunicorn

server {
    listen 80;
    server_name iptv2.quattre.com;

    access_log /var/log/nginx/iptv2.access.log;
    error_log  /var/log/nginx/iptv2.error.log;

    client_max_body_size 20m;

    # Para cuando se saque el certificado de Let's Encrypt.
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://192.168.100.11:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # Las listas largas de canales y las playlists de catchup pueden tardar.
        proxy_read_timeout 120s;
    }
}
