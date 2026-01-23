from django.urls import path
from . import views

app_name = 'stalker_api'

urlpatterns = [
    path('server/load.php', views.portal_handler, name='load'),
    path('c/', views.portal_handler, name='c'),
]
