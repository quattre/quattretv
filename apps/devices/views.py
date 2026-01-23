from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from .models import Device, DeviceMessage
from .serializers import DeviceSerializer, DeviceMessageSerializer


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['user', 'device_type', 'is_active']
    search_fields = ['mac_address', 'serial_number', 'name', 'user__username']

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_devices(self, request):
        """Get current user's devices."""
        devices = Device.objects.filter(user=request.user)
        serializer = self.get_serializer(devices, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def refresh_token(self, request, pk=None):
        """Generate new token for device."""
        device = self.get_object()
        token = device.refresh_token()
        return Response({'token': token})

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send message to device."""
        device = self.get_object()
        serializer = DeviceMessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(device=device)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def online(self, request):
        """Get all online devices."""
        threshold = timezone.now() - timezone.timedelta(minutes=5)
        devices = Device.objects.filter(
            is_active=True,
            last_seen__gte=threshold
        )
        serializer = self.get_serializer(devices, many=True)
        return Response(serializer.data)


class DeviceMessageViewSet(viewsets.ModelViewSet):
    queryset = DeviceMessage.objects.all()
    serializer_class = DeviceMessageSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['device', 'user', 'message_type', 'is_read']

    @action(detail=False, methods=['post'])
    def broadcast(self, request):
        """Send message to all devices."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(device=None, user=None)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
