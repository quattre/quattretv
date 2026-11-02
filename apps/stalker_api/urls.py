from django.urls import path
from . import views

# Sin app_name a proposito: este modulo se incluye en dos rutas distintas
# (stalker_portal/ y quattretv/stb/), y declarar un namespace repetido dejaba un
# aviso en cada arranque. Nadie resuelve estas URLs por nombre.

urlpatterns = [
    path('', views.portal_handler, name='root'),
    path('server/load.php', views.portal_handler, name='load'),
    path('c/', views.portal_handler, name='c'),
    # El portal de Ministra se recarga pidiendo c/index.html: un deco recien
    # pasado (ver handle_watchdog) llega por aqui la primera vez.
    path('c/index.html', views.portal_handler, name='c_index'),
]
