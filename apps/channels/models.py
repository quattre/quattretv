"""
Channel and category models.
"""
from django.db import models
from apps.core.models import TimeStampedModel, ActivableModel


class StreamType(models.TextChoices):
    HLS = 'hls', 'HLS'
    DASH = 'dash', 'DASH'
    RTSP = 'rtsp', 'RTSP'
    HTTP = 'http', 'HTTP/HTTPS'
    UDP = 'udp', 'UDP Multicast'


class CdnServer(TimeStampedModel, ActivableModel):
    """
    Un servidor de emisión (cdn10, cdn11...).

    Cada canal se emite desde uno: ffmpeg coge el multicast y escribe HLS, con
    una unidad systemd por canal (`ffmpeg-hls@<nombre>`). Aquí solo guardamos
    cómo llegar a él para poder ver qué está en marcha y reiniciar lo que se
    haya caído.
    """
    name = models.CharField(max_length=50, unique=True, help_text='cdn10, cdn11...')
    hls_base_url = models.URLField(
        max_length=300,
        help_text='Base del HLS, ej. http://cdn10.quattre.com:1500/hls/'
    )

    # Acceso para reiniciar canales. Sin esto el panel es solo de lectura.
    ssh_host = models.CharField(max_length=100, blank=True)
    ssh_port = models.PositiveIntegerField(default=22)
    ssh_user = models.CharField(max_length=50, default='quattre')

    systemd_unit = models.CharField(
        max_length=100,
        default='ffmpeg-hls@',
        help_text='Plantilla systemd; se le añade el nombre del canal en el CDN'
    )

    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'CDN'
        verbose_name_plural = 'CDNs'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def puede_reiniciar(self):
        return bool(self.ssh_host)

    def playlist_url(self, cdn_name):
        return f"{self.hls_base_url.rstrip('/')}/{cdn_name}/index.m3u8"


class Category(TimeStampedModel, ActivableModel):
    """Channel category/genre."""
    name = models.CharField(max_length=100)
    alias = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='categories/', blank=True, null=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    order = models.PositiveIntegerField(default=0)
    is_adult = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class ChannelPackage(TimeStampedModel, ActivableModel):
    """Channel package for tariffs."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Channel Package'
        verbose_name_plural = 'Channel Packages'

    def __str__(self):
        return self.name


class Channel(TimeStampedModel, ActivableModel):
    """TV Channel."""
    name = models.CharField(max_length=200)
    number = models.PositiveIntegerField(unique=True, db_index=True)
    logo = models.ImageField(upload_to='channels/logos/', blank=True, null=True)
    logo_url = models.URLField(blank=True, help_text='External logo URL')

    # Categorization
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='channels'
    )
    packages = models.ManyToManyField(
        ChannelPackage,
        blank=True,
        related_name='channels'
    )

    # Stream
    stream_url = models.URLField(max_length=500)
    stream_type = models.CharField(
        max_length=10,
        choices=StreamType.choices,
        default=StreamType.HLS
    )
    backup_stream_url = models.URLField(max_length=500, blank=True)
    # Emisión: en qué CDN vive este canal y con qué nombre
    cdn = models.ForeignKey(
        CdnServer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='channels'
    )
    cdn_name = models.CharField(
        max_length=100,
        blank=True,
        help_text='Nombre del canal en el CDN (el de ffmpeg-hls@<nombre> y el '
                  'del directorio HLS). Si se deja vacío se deduce de la URL.'
    )

    multicast_url = models.CharField(
        max_length=200,
        blank=True,
        help_text='Origen multicast para archivo/grabación, ej. udp://239.0.0.1:1234. '
                  'Es el mismo SRC del EnvironmentFile del CDN; los grabadores '
                  '(dumpstream) leen de aquí, no del HLS.'
    )

    # Features
    has_epg = models.BooleanField(default=True)
    has_timeshift = models.BooleanField(default=True)
    has_catchup = models.BooleanField(default=True)
    has_recording = models.BooleanField(default=True)
    is_hd = models.BooleanField(default=False)
    is_4k = models.BooleanField(default=False)
    is_adult = models.BooleanField(default=False)
    is_radio = models.BooleanField(default=False, help_text='Radio station instead of TV channel')

    # EPG mapping
    epg_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text='EPG channel ID for program guide'
    )

    # Timeshift settings
    timeshift_hours = models.PositiveIntegerField(
        default=24,
        help_text='Hours of timeshift/catchup available'
    )
    archive_hls_since = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Momento en que este canal empezo a archivarse en HLS. Lo '
                  'anterior a esta fecha sigue sirviendose del archivo antiguo '
                  'en MPEG-TS, asi que la migracion no deja huecos. Vacio = '
                  'todavia se archiva en MPEG-TS.'
    )

    # Metadata
    description = models.TextField(blank=True)
    country = models.CharField(max_length=2, blank=True, help_text='ISO country code')
    language = models.CharField(max_length=5, blank=True, help_text='ISO language code')

    class Meta:
        verbose_name = 'Channel'
        verbose_name_plural = 'Channels'
        ordering = ['number']

    def __str__(self):
        return f"{self.number}. {self.name}"

    @property
    def logo_display_url(self):
        """Return logo URL, preferring uploaded file over external URL."""
        if self.logo:
            return self.logo.url
        return self.logo_url or ''


class ChannelStream(TimeStampedModel, ActivableModel):
    """Multiple streams per channel for different qualities/protocols."""
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name='streams'
    )
    name = models.CharField(max_length=100, help_text='e.g., HD, SD, Mobile')
    url = models.URLField(max_length=500)
    stream_type = models.CharField(
        max_length=10,
        choices=StreamType.choices,
        default=StreamType.HLS
    )
    quality = models.CharField(
        max_length=20,
        choices=[
            ('4k', '4K Ultra HD'),
            ('1080p', '1080p Full HD'),
            ('720p', '720p HD'),
            ('480p', '480p SD'),
            ('360p', '360p'),
            ('auto', 'Auto'),
        ],
        default='auto'
    )
    priority = models.PositiveIntegerField(default=0, help_text='Higher = preferred')

    class Meta:
        verbose_name = 'Channel Stream'
        verbose_name_plural = 'Channel Streams'
        ordering = ['-priority']

    def __str__(self):
        return f"{self.channel.name} - {self.name}"


class Favorite(TimeStampedModel):
    """User's favorite channels."""
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='favorite_channels'
    )
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Favorite'
        verbose_name_plural = 'Favorites'
        unique_together = ['user', 'channel']
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.channel.name}"
