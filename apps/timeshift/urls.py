from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'timeshift'

router = DefaultRouter()
router.register(r'', views.TimeshiftViewSet, basename='timeshift')

urlpatterns = [
    path('', include(router.urls)),
]
