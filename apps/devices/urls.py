from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'devices'

router = DefaultRouter()
router.register(r'', views.DeviceViewSet)
router.register(r'messages', views.DeviceMessageViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
