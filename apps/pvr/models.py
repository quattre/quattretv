"""
PVR (Personal Video Recorder) models.
"""
from django.db import models
from apps.core.models import TimeStampedModel


class RecordingStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    RECORDING = 'recording', 'Recording'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class Recording(TimeStampedModel):
    """Scheduled or completed recording."""
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='recordings'
    )
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.CASCADE,
        related_name='recordings'
    )
    program = models.ForeignKey(
        'epg.Program',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recordings'
    )

    # Recording details
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    # Status
    status = models.CharField(
        max_length=20,
        choices=RecordingStatus.choices,
        default=RecordingStatus.SCHEDULED
    )
    error_message = models.TextField(blank=True)

    # File info (for completed recordings)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    stream_url = models.URLField(max_length=500, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True, help_text='Duration in seconds')

    # Options
    pre_padding = models.PositiveIntegerField(default=0, help_text='Minutes before start')
    post_padding = models.PositiveIntegerField(default=0, help_text='Minutes after end')

    class Meta:
        verbose_name = 'Recording'
        verbose_name_plural = 'Recordings'
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def actual_start_time(self):
        from datetime import timedelta
        return self.start_time - timedelta(minutes=self.pre_padding)

    @property
    def actual_end_time(self):
        from datetime import timedelta
        return self.end_time + timedelta(minutes=self.post_padding)


class RecordingRule(TimeStampedModel):
    """Auto-recording rules (series recording)."""
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='recording_rules'
    )
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    # Match criteria
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recording_rules'
    )
    title_contains = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=100, blank=True)

    # Options
    pre_padding = models.PositiveIntegerField(default=0)
    post_padding = models.PositiveIntegerField(default=5)
    keep_recordings = models.PositiveIntegerField(
        default=0,
        help_text='Number of recordings to keep (0 = unlimited)'
    )

    class Meta:
        verbose_name = 'Recording Rule'
        verbose_name_plural = 'Recording Rules'

    def __str__(self):
        return self.name

    def matches_program(self, program):
        """Check if a program matches this rule."""
        if self.channel and program.channel_id != self.channel_id:
            return False
        if self.title_contains and self.title_contains.lower() not in program.title.lower():
            return False
        if self.category and self.category.lower() != program.category.lower():
            return False
        return True
