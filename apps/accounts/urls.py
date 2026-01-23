from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views

app_name = 'accounts'

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'tariffs', views.TariffViewSet)
router.register(r'sessions', views.UserSessionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
