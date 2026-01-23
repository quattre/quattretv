from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'channels'

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet)
router.register(r'', views.ChannelViewSet, basename='channel')
router.register(r'packages', views.ChannelPackageViewSet)
router.register(r'streams', views.ChannelStreamViewSet)
router.register(r'favorites', views.FavoriteViewSet, basename='favorite')

urlpatterns = [
    path('', include(router.urls)),
]
