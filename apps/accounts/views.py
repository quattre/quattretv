from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import User, Tariff, UserSession
from .serializers import UserSerializer, TariffSerializer, UserSessionSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['is_active', 'tariff']
    search_fields = ['username', 'email', 'first_name', 'last_name']

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def extend_subscription(self, request, pk=None):
        """Extend user subscription by tariff duration."""
        user = self.get_object()
        if not user.tariff:
            return Response(
                {'error': 'User has no tariff assigned'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.utils import timezone
        from datetime import timedelta

        base = user.subscription_expires or timezone.now()
        if base < timezone.now():
            base = timezone.now()

        user.subscription_expires = base + timedelta(days=user.tariff.duration_days)
        user.save()

        return Response({'subscription_expires': user.subscription_expires})


class TariffViewSet(viewsets.ModelViewSet):
    queryset = Tariff.objects.filter(is_active=True)
    serializer_class = TariffSerializer
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        if self.action == 'list':
            return [IsAuthenticated()]
        return super().get_permissions()


class UserSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserSession.objects.all()
    serializer_class = UserSessionSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['user', 'device', 'is_active']

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_sessions(self, request):
        """Get current user's sessions."""
        sessions = UserSession.objects.filter(user=request.user, is_active=True)
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)
