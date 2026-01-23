from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Recording, RecordingRule, RecordingStatus
from .serializers import (
    RecordingSerializer, RecordingCreateSerializer, RecordingRuleSerializer
)


class RecordingViewSet(viewsets.ModelViewSet):
    serializer_class = RecordingSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['channel', 'status']
    search_fields = ['title']

    def get_queryset(self):
        return Recording.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return RecordingCreateSerializer
        return RecordingSerializer

    @action(detail=False, methods=['get'])
    def scheduled(self, request):
        """Get scheduled recordings."""
        recordings = self.get_queryset().filter(
            status=RecordingStatus.SCHEDULED,
            start_time__gte=timezone.now()
        )
        serializer = self.get_serializer(recordings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def completed(self, request):
        """Get completed recordings."""
        recordings = self.get_queryset().filter(status=RecordingStatus.COMPLETED)
        serializer = self.get_serializer(recordings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recording(self, request):
        """Get currently recording."""
        recordings = self.get_queryset().filter(status=RecordingStatus.RECORDING)
        serializer = self.get_serializer(recordings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a scheduled recording."""
        recording = self.get_object()
        if recording.status not in [RecordingStatus.SCHEDULED, RecordingStatus.RECORDING]:
            return Response(
                {'error': 'Cannot cancel this recording'},
                status=status.HTTP_400_BAD_REQUEST
            )

        recording.status = RecordingStatus.CANCELLED
        recording.save()
        return Response(self.get_serializer(recording).data)

    @action(detail=True, methods=['delete'])
    def delete_file(self, request, pk=None):
        """Delete recording file."""
        recording = self.get_object()
        if recording.status != RecordingStatus.COMPLETED:
            return Response(
                {'error': 'Recording is not completed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Actually delete file from storage
        recording.file_path = ''
        recording.stream_url = ''
        recording.save()
        return Response({'status': 'File deleted'})

    @action(detail=False, methods=['post'])
    def record_program(self, request):
        """Schedule recording from EPG program."""
        program_id = request.data.get('program_id')
        if not program_id:
            return Response(
                {'error': 'program_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.epg.models import Program
        try:
            program = Program.objects.get(id=program_id)
        except Program.DoesNotExist:
            return Response(
                {'error': 'Program not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if already scheduled
        existing = Recording.objects.filter(
            user=request.user,
            program=program
        ).exists()
        if existing:
            return Response(
                {'error': 'Recording already scheduled'},
                status=status.HTTP_400_BAD_REQUEST
            )

        recording = Recording.objects.create(
            user=request.user,
            channel=program.channel,
            program=program,
            title=program.title,
            description=program.description,
            start_time=program.start_time,
            end_time=program.end_time,
        )

        return Response(
            RecordingSerializer(recording).data,
            status=status.HTTP_201_CREATED
        )


class RecordingRuleViewSet(viewsets.ModelViewSet):
    serializer_class = RecordingRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RecordingRule.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle rule active status."""
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save()
        return Response(self.get_serializer(rule).data)
