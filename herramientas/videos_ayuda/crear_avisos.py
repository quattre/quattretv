from apps.devices.models import Aviso

GUIAS = [
    dict(orden=0, al_iniciar=True, veces=3, imagen='ayuda/bienvenida.jpg', video_url='ayuda/novedades.mp4',
         titulo='Bienvenido: lo nuevo',
         texto='Hemos renovado la televisión. Lo nuevo:\n\n'
               '·  VIDEOCLUB 7 DÍAS (tecla amarilla): películas y series de la última semana, cuando quieras.\n'
               '·  ¿Te lo has perdido? En la guía (tecla verde), OK y lo ves desde el principio.\n'
               '·  Viendo un canal, ◀ vuelve atrás en el tiempo y OK lo pausa.\n\n'
               'Míralo en el vídeo: son dos minutos. Lo tienes siempre en Menú → Ayuda.'),
    dict(orden=1, imagen='ayuda/videoclub.jpg', video_url='ayuda/videoclub.mp4',
         titulo='Videoclub 7 días',
         texto='Todo lo emitido en los últimos 7 días, para verlo cuando quieras.\n\n'
               '·  Se abre con la tecla amarilla o desde el menú.\n'
               '·  ◀▶ recorres cada fila; ▲▼ cambias de fila. Arriba, las pestañas: Películas, Series, Infantil…\n'
               '·  OK en una serie te enseña todos sus capítulos.\n'
               '·  Viéndolo: ◀▶ retrocede o avanza 30 segundos (más si repites). OK saca la barra y, con ella puesta, pausa.\n'
               '·  Lo que dejas a medias sigue en «Seguir viendo».\n\n'
               'Empieza a la hora que marca la cadena. Alguna pone un minuto de anuncios propios antes de la película: pulsa ▶ para saltarlos.'),
    dict(orden=2, imagen='ayuda/guia.jpg', video_url='ayuda/guia.mp4',
         titulo='La guía y lo ya emitido',
         texto='·  En la lista de canales, ▶ (o la tecla azul) abre la guía del canal.\n'
               '·  ▲▼ te mueves por el día. Lo que se emite ahora sale marcado.\n'
               '·  En algo ya emitido, OK lo ves desde el principio (en los canales que lo permiten).\n'
               '·  ▶ abre la ficha con toda la información del programa.\n'
               '·  ◀ vuelve atrás.'),
    dict(orden=3, imagen='ayuda/menu.jpg',
         titulo='Tus canales favoritos',
         texto='·  En la lista de canales, ponte en uno y pulsa la tecla verde: queda en tus favoritos. Otra vez, se quita.\n'
               '·  Para ver solo tus favoritos: Menú → Solo favoritos. Para volver a verlos todos, lo mismo otra vez.\n'
               '·  En el menú, Categorías te enseña los canales por temas: deportes, cine, infantil…'),
    dict(orden=4,
         titulo='Grabar un programa',
         texto='Si tu servicio incluye grabaciones:\n\n'
               '·  Tecla roja: graba lo que estás viendo. Otra vez, para la grabación.\n'
               '·  En la guía, OK sobre un programa que aún no ha empezado lo deja programado.\n'
               '·  Tus grabaciones están en Menú → Mis grabaciones.'),
    dict(orden=5,
         titulo='Si algo no va bien',
         texto='·  Si un canal se queda en negro, cambia a otro y vuelve.\n'
               '·  Atrás siempre te devuelve a la pantalla anterior.\n'
               '·  Si el aparato no responde, desenchúfalo 10 segundos y vuelve a enchufarlo.\n'
               '·  Si sigue sin ir, llámanos y dinos qué canal y a qué hora pasó.'),
]

for g in GUIAS:
    a, nuevo = Aviso.objects.get_or_create(titulo=g['titulo'])
    a.texto = g['texto']
    a.orden = g['orden']
    a.al_iniciar = g.get('al_iniciar', False)
    a.veces = g.get('veces', 0)
    a.en_ayuda = True
    a.activo = True
    a.video_url = g.get('video_url', '')
    a.imagen = g.get('imagen', '')
    a.save()
    print('creado' if nuevo else 'actualizado', a.id, a.titulo)
