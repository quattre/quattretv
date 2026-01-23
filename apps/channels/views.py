from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q
from .models import Category, Channel, ChannelPackage, ChannelStream, Favorite
from .serializers import (
    CategorySerializer, ChannelListSerializer, ChannelDetailSerializer,
    ChannelPackageSerializer, ChannelStreamSerializer, FavoriteSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    filterset_fields = ['parent', 'is_adult']
    search_fields = ['name', 'alias']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.filter(is_active=True)
    filterset_fields = ['category', 'is_hd', 'is_4k', 'is_adult', 'has_epg', 'has_timeshift']
    search_fields = ['name', 'number', 'epg_id']
    ordering_fields = ['number', 'name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ChannelDetailSerializer
        return ChannelListSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Filter by user's tariff packages
        if user.is_authenticated and not user.is_staff:
            if user.tariff:
                package_ids = user.tariff.channel_packages.values_list('id', flat=True)
                queryset = queryset.filter(
                    Q(packages__id__in=package_ids) | Q(packages__isnull=True)
                ).distinct()

            # Filter adult content
            if not user.parental_password:
                queryset = queryset.filter(is_adult=False)

        return queryset

    @action(detail=True, methods=['get'])
    def stream_url(self, request, pk=None):
        """Get stream URL for playback with authentication."""
        channel = self.get_object()
        # TODO: Generate authenticated stream URL with token
        return Response({
            'url': channel.stream_url,
            'backup_url': channel.backup_stream_url,
            'type': channel.stream_type,
        })

    @action(detail=False, methods=['get'])
    def by_number(self, request):
        """Get channel by number."""
        number = request.query_params.get('number')
        if not number:
            return Response(
                {'error': 'number parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            channel = self.get_queryset().get(number=number)
            serializer = ChannelDetailSerializer(channel)
            return Response(serializer.data)
        except Channel.DoesNotExist:
            return Response(
                {'error': 'Channel not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ChannelPackageViewSet(viewsets.ModelViewSet):
    queryset = ChannelPackage.objects.filter(is_active=True)
    serializer_class = ChannelPackageSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['get'])
    def channels(self, request, pk=None):
        """Get all channels in this package."""
        package = self.get_object()
        channels = package.channels.filter(is_active=True)
        serializer = ChannelListSerializer(channels, many=True)
        return Response(serializer.data)


class ChannelStreamViewSet(viewsets.ModelViewSet):
    queryset = ChannelStream.objects.filter(is_active=True)
    serializer_class = ChannelStreamSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['channel', 'stream_type', 'quality']


class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Toggle favorite status for a channel."""
        channel_id = request.data.get('channel_id')
        if not channel_id:
            return Response(
                {'error': 'channel_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            channel_id=channel_id
        )

        if not created:
            favorite.delete()
            return Response({'status': 'removed'})

        return Response({'status': 'added', 'id': favorite.id})
