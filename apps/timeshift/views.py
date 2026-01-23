from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .models import TimeshiftArchive
from .serializers import TimeshiftArchiveSerializer


class TimeshiftViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TimeshiftArchive.objects.all()
    serializer_class = TimeshiftArchiveSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['channel']

    @action(detail=False, methods=['get'])
    def get_url(self, request):
        """Get timeshift stream URL for a specific time."""
        channel_id = request.query_params.get('channel')
        timestamp = request.query_params.get('timestamp')

        if not channel_id:
            return Response(
                {'error': 'channel parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.channels.models import Channel
        try:
            channel = Channel.objects.get(id=channel_id, is_active=True)
        except Channel.DoesNotExist:
            return Response(
                {'error': 'Channel not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not channel.has_timeshift:
            return Response(
                {'error': 'Timeshift not available for this channel'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check user's tariff allows timeshift
        user = request.user
        if user.tariff and not user.tariff.has_timeshift:
            return Response(
                {'error': 'Timeshift not included in your subscription'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Generate timeshift URL
        # Format depends on streaming server implementation
        # Common formats: ?utc=TIMESTAMP or /timeshift/CHANNEL/TIMESTAMP
        base_url = channel.stream_url
        timeshift_url = f"{base_url}?utc={timestamp}" if timestamp else base_url

        return Response({
            'url': timeshift_url,
            'channel_id': channel_id,
            'timestamp': timestamp,
            'max_hours': channel.timeshift_hours,
        })

    @action(detail=False, methods=['get'])
    def catchup(self, request):
        """Get catchup program URL."""
        channel_id = request.query_params.get('channel')
        program_id = request.query_params.get('program')

        if not channel_id or not program_id:
            return Response(
                {'error': 'channel and program parameters required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.epg.models import Program
        try:
            program = Program.objects.get(id=program_id, channel_id=channel_id)
        except Program.DoesNotExist:
            return Response(
                {'error': 'Program not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if program is within catchup window
        max_hours = program.channel.timeshift_hours
        cutoff = timezone.now() - timedelta(hours=max_hours)

        if program.start_time < cutoff:
            return Response(
                {'error': 'Program is no longer available for catchup'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate catchup URL
        start_ts = int(program.start_time.timestamp())
        end_ts = int(program.end_time.timestamp())
        base_url = program.channel.stream_url

        return Response({
            'url': f"{base_url}?utc={start_ts}&lutc={end_ts}",
            'program': {
                'id': program.id,
                'title': program.title,
                'start_time': program.start_time,
                'end_time': program.end_time,
            }
        })

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get channels with timeshift available."""
        from apps.channels.models import Channel

        channels = Channel.objects.filter(
            is_active=True,
            has_timeshift=True
        ).values('id', 'name', 'number', 'timeshift_hours')

        return Response(list(channels))
