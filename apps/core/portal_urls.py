"""
Portal URL configuration.
"""
from django.urls import path
from . import portal_views as views

app_name = 'portal'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Users
    path('users/', views.users_list, name='users'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/devices/', views.user_devices, name='user_devices'),
    path('users/<int:user_id>/renew/', views.user_renew, name='user_renew'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),

    # Devices
    path('devices/', views.devices_list, name='devices'),
    path('devices/create/', views.device_create, name='device_create'),
    path('devices/<int:device_id>/', views.device_edit, name='device_edit'),
    path('devices/<int:device_id>/refresh-token/', views.device_refresh_token, name='device_refresh_token'),
    path('devices/<int:device_id>/delete/', views.device_delete, name='device_delete'),

    # Channels
    path('channels/', views.channels_list, name='channels'),
    path('channels/create/', views.channel_create, name='channel_create'),
    path('channels/import/', views.channels_import, name='channels_import'),
    path('channels/<int:channel_id>/', views.channel_edit, name='channel_edit'),
    path('channels/<int:channel_id>/delete/', views.channel_delete, name='channel_delete'),

    # Categories
    path('categories/', views.categories_list, name='categories'),

    # Tariffs
    path('tariffs/', views.tariffs_list, name='tariffs'),

    # EPG
    path('epg/', views.epg_list, name='epg'),

    # VOD
    path('vod/', views.vod_list, name='vod'),

    # Streams
    path('streams/', views.streams_list, name='streams'),

    # Logs
    path('logs/', views.logs_list, name='logs'),

    # Settings
    path('settings/', views.settings_view, name='settings'),
]
