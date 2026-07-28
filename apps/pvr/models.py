"""
PVR (Personal Video Recorder) models.
"""
from django.db import models
from apps.core.models import TimeStampedModel


class StorageRole(models.TextChoices):
    ARCHIVE = 'archive', 'Archivo/catchup (storage1)'
    RECORDS = 'records', 'Grabaciones de cliente (record1)'
    BOTH = 'both', 'Ambos'


class StorageServer(TimeStampedModel):
    """
    A Ministra-style storage server (record1 / storage1).

    We do not record anything ourselves: these boxes run `dumpstream` from
    /var/www/stalker_portal/storage. They pull their archive tasks from us and
    we push per-recording commands to their REST endpoint.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='STORAGE_NAME configurado en el config.php del servidor'
    )
    role = models.CharField(
        max_length=10,
        choices=StorageRole.choices,
        default=StorageRole.BOTH
    )
    api_url = models.URLField(
        max_length=300,
        help_text='Base REST del storage, ej. http://storage1.quattre.com/storage/ '
                  '(ahí viven rest.php y get.php)'
    )
    playback_url = models.URLField(
        max_length=300,
        blank=True,
        help_text='Base pública para reproducir (get.php). Si se deja vacía se usa api_url'
    )
    token = models.CharField(
        max_length=128,
        blank=True,
        help_text='Token compartido: se envía como Bearer y se valida en chk_storage_token.php'
    )
    archive_path = models.CharField(
        max_length=100,
        default='archive_hls',
        help_text='Subdirectorio (servido por nginx con autoindex json) donde el '
                  'grabador deja los segmentos HLS del archivo'
    )
    records_hls = models.BooleanField(
        default=False,
        help_text='El grabador de este servidor ya escribe HLS en vez de MPEG-TS. '
                  'Se activa canal a canal; mientras esté desactivado todo sigue '
                  'como hasta ahora.'
    )
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Última vez que el storage pidió sus tareas de archivo'
    )

    class Meta:
        verbose_name = 'Storage Server'
        verbose_name_plural = 'Storage Servers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    @property
    def records_archive(self):
        return self.role in (StorageRole.ARCHIVE, StorageRole.BOTH)

    @property
    def records_clients(self):
        return self.role in (StorageRole.RECORDS, StorageRole.BOTH)

    def build_url(self, path, public=False):
        base = (self.playback_url if public and self.playback_url else self.api_url)
        return f"{base.rstrip('/')}/{path.lstrip('/')}"


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

    # Storage handling this recording (record1 & friends)
    storage = models.ForeignKey(
        StorageServer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recordings'
    )
    filename = models.CharField(
        max_length=300,
        blank=True,
        help_text='Fichero devuelto por el grabador'
    )
    container = models.CharField(
        max_length=4,
        choices=[('ts', 'MPEG-TS'), ('hls', 'HLS')],
        default='ts',
        help_text='Formato con el que se grabo. Se fija al enviarla al '
                  'grabador, para que las grabaciones antiguas se sigan '
                  'reproduciendo despues de migrar.'
    )

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
