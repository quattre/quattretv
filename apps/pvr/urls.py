from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'pvr'

router = DefaultRouter()
router.register(r'recordings', views.RecordingViewSet, basename='recording')
router.register(r'rules', views.RecordingRuleViewSet, basename='rule')

urlpatterns = [
    path('', include(router.urls)),
]
