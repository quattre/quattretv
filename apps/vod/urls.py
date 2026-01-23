from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'vod'

router = DefaultRouter()
router.register(r'categories', views.VodCategoryViewSet)
router.register(r'movies', views.MovieViewSet)
router.register(r'series', views.SeriesViewSet)
router.register(r'seasons', views.SeasonViewSet)
router.register(r'episodes', views.EpisodeViewSet)
router.register(r'history', views.WatchHistoryViewSet, basename='history')

urlpatterns = [
    path('', include(router.urls)),
]
