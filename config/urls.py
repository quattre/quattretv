"""
URL configuration for QuattreTV.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Portal Admin (Stalker-style)
    path('portal/', include('apps.core.portal_urls')),

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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin site customization
admin.site.site_header = 'QuattreTV Administration'
admin.site.site_title = 'QuattreTV Admin'
admin.site.index_title = 'IPTV Middleware Management'
