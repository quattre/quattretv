"""
Timeshift / Catchup models.
"""
from django.db import models
from apps.core.models import TimeStampedModel


class TimeshiftArchive(TimeStampedModel):
    """Timeshift archive segments for a channel."""
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.CASCADE,
        related_name='timeshift_archives'
    )
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    stream_url = models.URLField(max_length=500)
    duration = models.PositiveIntegerField(help_text='Duration in seconds')

    class Meta:
        verbose_name = 'Timeshift Archive'
        verbose_name_plural = 'Timeshift Archives'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['channel', 'start_time']),
        ]

    def __str__(self):
        return f"{self.channel.name} - {self.start_time}"
