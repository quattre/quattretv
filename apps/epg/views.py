from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from datetime import timedelta
from .models import EpgSource, Program
from .serializers import EpgSourceSerializer, ProgramSerializer, ProgramCompactSerializer


class EpgSourceViewSet(viewsets.ModelViewSet):
    queryset = EpgSource.objects.all()
    serializer_class = EpgSourceSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['post'])
    def update_now(self, request, pk=None):
        """Trigger EPG update for this source."""
        source = self.get_object()
        from .tasks import update_epg_source
        update_epg_source.delay(source.id)
        return Response({'status': 'Update scheduled'})


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Program.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_fields = ['channel', 'category']
    search_fields = ['title', 'description']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProgramSerializer
        return ProgramCompactSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by date range
        date = self.request.query_params.get('date')
        if date:
            from datetime import datetime
            try:
                day = datetime.strptime(date, '%Y-%m-%d').date()
                queryset = queryset.filter(
                    start_time__date=day
                )
            except ValueError:
                pass

        return queryset.select_related('channel')

    @action(detail=False, methods=['get'])
    def now(self, request):
        """Get currently playing programs."""
        now = timezone.now()
        programs = Program.objects.filter(
            start_time__lte=now,
            end_time__gte=now
        ).select_related('channel')

        channel_id = request.query_params.get('channel')
        if channel_id:
            programs = programs.filter(channel_id=channel_id)

        serializer = ProgramSerializer(programs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def schedule(self, request):
        """Get EPG schedule for a channel."""
        channel_id = request.query_params.get('channel')
        if not channel_id:
            return Response(
                {'error': 'channel parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        hours = int(request.query_params.get('hours', 24))
        now = timezone.now()
        end = now + timedelta(hours=hours)

        programs = Program.objects.filter(
            channel_id=channel_id,
            end_time__gte=now,
            start_time__lte=end
        ).order_by('start_time')

        serializer = ProgramSerializer(programs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def grid(self, request):
        """Get EPG grid for multiple channels."""
        channel_ids = request.query_params.getlist('channels')
        hours = int(request.query_params.get('hours', 6))

        now = timezone.now()
        start = now - timedelta(hours=1)  # Include current program
        end = now + timedelta(hours=hours)

        queryset = Program.objects.filter(
            end_time__gte=start,
            start_time__lte=end
        ).select_related('channel').order_by('channel__number', 'start_time')

        if channel_ids:
            queryset = queryset.filter(channel_id__in=channel_ids)

        # Group by channel
        grid = {}
        for program in queryset:
            channel_id = str(program.channel_id)
            if channel_id not in grid:
                grid[channel_id] = {
                    'channel_id': program.channel_id,
                    'channel_name': program.channel.name,
                    'channel_number': program.channel.number,
                    'programs': []
                }
            grid[channel_id]['programs'].append(
                ProgramCompactSerializer(program).data
            )

        return Response(list(grid.values()))
