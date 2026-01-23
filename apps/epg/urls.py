from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'epg'

router = DefaultRouter()
router.register(r'sources', views.EpgSourceViewSet)
router.register(r'programs', views.ProgramViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
