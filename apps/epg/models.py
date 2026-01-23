"""
EPG (Electronic Program Guide) models.
"""
from django.db import models
from apps.core.models import TimeStampedModel


class EpgSource(TimeStampedModel):
    """EPG data source configuration."""
    name = models.CharField(max_length=100)
    url = models.URLField(max_length=500, help_text='XMLTV source URL')
    is_active = models.BooleanField(default=True)
    last_update = models.DateTimeField(null=True, blank=True)
    update_interval = models.PositiveIntegerField(
        default=3600,
        help_text='Update interval in seconds'
    )
    auto_update = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'EPG Source'
        verbose_name_plural = 'EPG Sources'

    def __str__(self):
        return self.name


class Program(models.Model):
    """TV Program/Show."""
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.CASCADE,
        related_name='programs'
    )
    epg_id = models.CharField(max_length=100, db_index=True)

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)

    # Metadata
    category = models.CharField(max_length=100, blank=True)
    episode_title = models.CharField(max_length=500, blank=True)
    season = models.PositiveIntegerField(null=True, blank=True)
    episode = models.PositiveIntegerField(null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    rating = models.CharField(max_length=20, blank=True)
    poster = models.URLField(max_length=500, blank=True)
    icon = models.URLField(max_length=500, blank=True)

    # Flags
    is_live = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_premiere = models.BooleanField(default=False)
    has_subtitles = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Program'
        verbose_name_plural = 'Programs'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['channel', 'start_time']),
            models.Index(fields=['epg_id', 'start_time']),
        ]

    def __str__(self):
        return f"{self.channel.name} - {self.title} ({self.start_time})"

    @property
    def duration_minutes(self):
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)

    @property
    def is_current(self):
        from django.utils import timezone
        now = timezone.now()
        return self.start_time <= now <= self.end_time

    @property
    def progress_percent(self):
        from django.utils import timezone
        now = timezone.now()
        if now < self.start_time:
            return 0
        if now > self.end_time:
            return 100
        elapsed = (now - self.start_time).total_seconds()
        total = (self.end_time - self.start_time).total_seconds()
        return int((elapsed / total) * 100)
