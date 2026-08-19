"""
URL configuration for QuattreTV.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.health import health, ping
from apps.stalker_api import storage_urls

urlpatterns = [
    path('admin/', admin.site.urls),

    # Salud del servicio (para monitorizacion)
    path('health', health, name='health'),
    path('ping', ping, name='ping'),
    path('health/', health),

    # API v1
    path('api/v1/', include('apps.core.urls')),
    path('api/v1/accounts/', include('apps.accounts.urls')),
    path('api/v1/devices/', include('apps.devices.urls')),
    path('api/v1/channels/', include('apps.channels.urls')),
    path('api/v1/epg/', include('apps.epg.urls')),
    path('api/v1/vod/', include('apps.vod.urls')),
    path('api/v1/timeshift/', include('apps.timeshift.urls')),
    path('api/v1/pvr/', include('apps.pvr.urls')),

    # Stalker Portal compatible API
    path('stalker_portal/', include('apps.stalker_api.urls')),
    path('portal.php', include('apps.stalker_api.portal_urls')),

    # Servidores de grabación (record1 / storage1): piden sus tareas de archivo
    # y avisan del estado de las grabaciones. API_URL del storage debe apuntar
    # aquí, y PORTAL_URL a la raíz para los chk_*.php.
    path('storage_api/', include('apps.stalker_api.storage_urls')),
    path('server/api/', include(
        (storage_urls.portal_api_urlpatterns, 'storage_api'), namespace='storage_api'
    )),

    # QuattreTV STB endpoint (alternativa a stalker_portal)
    path('quattretv/stb/', include('apps.stalker_api.urls')),
    path('quattretv/stb/portal.php', include('apps.stalker_api.portal_urls')),

    # Portal Admin (en la raíz - al final para no interferir con APIs)
    path('', include('apps.core.portal_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin site customization
admin.site.site_header = 'QuattreTV Administration'
admin.site.site_title = 'QuattreTV Admin'
admin.site.index_title = 'IPTV Middleware Management'
