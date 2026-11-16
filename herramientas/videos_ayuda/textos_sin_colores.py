from apps.devices.models import Aviso

TEXTOS = {
    'Bienvenido: lo nuevo':
        'Hemos renovado la televisión. Lo nuevo:\n\n'
        '·  VIDEOCLUB 7 DÍAS (tecla amarilla): películas y series de la última semana, cuando quieras.\n'
        '·  ¿Te lo has perdido? En la guía (tecla verde), OK y lo ves desde el principio.\n'
        '·  Viendo un canal, ◀ vuelve atrás en el tiempo y OK lo pausa.\n\n'
        'Míralo en el vídeo: son dos minutos. Lo tienes siempre en Menú → Ayuda.',
    'Videoclub 7 días':
        'Todo lo emitido en los últimos 7 días, para verlo cuando quieras.\n\n'
        '·  Se abre desde el menú de la izquierda: Videoclub 7 días.\n'
        '·  ◀▶ recorres cada fila; ▲▼ cambias de fila. Arriba, las pestañas: Películas, Series, Infantil…\n'
        '·  OK en una serie te enseña todos sus capítulos.\n'
        '·  Viéndolo: ◀▶ retrocede o avanza 30 segundos (más si repites). OK saca la barra y, con ella puesta, pausa.\n'
        '·  Lo que dejas a medias sigue en «Seguir viendo».\n\n'
        'Empieza a la hora que marca la cadena. Alguna pone un minuto de anuncios propios antes de la película: pulsa ▶ para saltarlos.',
    'La guía y lo ya emitido':
        '·  En la lista de canales, ▶ abre la guía del canal (también está en el menú de la izquierda).\n'
        '·  ▲▼ te mueves por el día. Lo que se emite ahora sale marcado.\n'
        '·  En algo ya emitido, OK lo ves desde el principio (en los canales que lo permiten).\n'
        '·  ▶ abre la ficha con toda la información del programa.\n'
        '·  ◀ vuelve atrás.',
    'Grabar un programa':
        'Si tu servicio incluye grabaciones:\n\n'
        '·  En la guía, elige el programa y pulsa OK: si aún no ha empezado queda programado, y si se está emitiendo empieza a grabarse.\n'
        '·  OK otra vez sobre el mismo programa para pararla o quitarla.\n'
        '·  Tus grabaciones están en el menú de la izquierda: Mis grabaciones.',
    'Si algo no va bien':
        '·  Si un canal se queda en negro, cambia a otro y vuelve.\n'
        '·  Atrás siempre te devuelve a la pantalla anterior.\n'
        '·  Si el aparato no responde, desenchúfalo 10 segundos y vuelve a enchufarlo.\n'
        '·  Si sigue sin ir, escríbenos a adm@quattre.com o entra en quattre.com, y dinos qué canal y a qué hora pasó.',
}
for titulo, texto in TEXTOS.items():
    a = Aviso.objects.get(titulo=titulo)
    a.texto = texto
    a.save()
    print('actualizado', titulo)

c, nuevo = Aviso.objects.get_or_create(titulo='Contacto', defaults={'orden': 6})
c.texto = ('¿Necesitas ayuda o quieres contarnos algo?\n\n'
           '·  Web: quattre.com\n'
           '·  Email: adm@quattre.com')
c.en_ayuda, c.al_iniciar, c.activo, c.veces, c.orden = True, False, True, 0, 6
c.save()
print('creado' if nuevo else 'actualizado', 'Contacto')
for a in Aviso.objects.all():
    a.save()
