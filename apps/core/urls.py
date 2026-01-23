from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('info/', views.server_info, name='server_info'),
]
