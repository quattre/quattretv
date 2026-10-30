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
    controlado_por_ministra = models.BooleanField(
        default=False,
        help_text='Lo sigue mandando Ministra: aqui solo se leen sus ficheros '
                  '(grabaciones antiguas, archivo) y nunca se le da una orden.'
    )
    secure_link_secret = models.CharField(
        max_length=100,
        blank=True,
        help_text='Secreto del secure_link del nginx del grabador, si sirve los '
                  '.mpg firmados (en los de Ministra viene "supersecret"). '
                  'Vacio = enlaces sin firmar.'
    )
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Última vez que el storage pidió sus tareas de archivo'
    )

    # Acceso para vigilar disco, memoria y carga
    ssh_host = models.CharField(max_length=100, blank=True)
    ssh_port = models.PositiveIntegerField(default=22)
    ssh_user = models.CharField(max_length=50, default='quattre')

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

    def enlace_firmado(self, fichero, ip_cliente, validez=6 * 3600):
        """
        Direccion de un fichero servido con el secure_link de nginx.

        Es la misma cuenta que hace el nginx de los grabadores de Ministra:
        md5(secreto + uri + ip + caducidad) en base64 para url. Va atada a la
        IP del aparato, asi que el enlace no sirve si se pasa a otro.
        """
        import base64
        import hashlib
        import time
        from urllib.parse import urlparse

        url = self.build_url(fichero, public=True)
        if not self.secure_link_secret:
            return url
        caduca = int(time.time()) + validez
        uri = urlparse(url).path
        firma = hashlib.md5(
            f'{self.secure_link_secret}{uri}{ip_cliente}{caduca}'.encode()
        ).digest()
        firma = base64.urlsafe_b64encode(firma).decode().rstrip('=')
        return f'{url}?st={firma}&e={caduca}'


class AjustesGrabacion(models.Model):
    """
    Los limites de las grabaciones de los clientes, que se cambian desde el
    panel (Configuracion). Una sola fila; si no existe, valen los de
    settings.QUATTRETV (los mismos que tenia Ministra).
    """
    horas_por_cliente = models.PositiveIntegerField(
        default=30, help_text='Horas que puede guardar cada cliente entre todas. 0 = sin limite')
    horas_por_grabacion = models.PositiveIntegerField(
        default=3, help_text='Lo mas que dura una grabacion. 0 = sin limite')
    meses_conservar = models.PositiveIntegerField(
        default=12, help_text='Meses que se guarda cada grabacion antes de borrarse sola. 0 = para siempre')
    dias_aviso = models.PositiveIntegerField(
        default=7, help_text='Dias antes de borrarse en que se avisa al arrancar. 0 = no avisar')
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ajustes de grabacion'
        verbose_name_plural = 'Ajustes de grabacion'

    CLAVE_CACHE = 'pvr:ajustes'

    def save(self, *args, **kwargs):
        from django.core.cache import cache
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CLAVE_CACHE)

    @classmethod
    def actual(cls):
        """Los ajustes en minutos y dias, como los usa el resto del codigo."""
        from django.conf import settings
        from django.core.cache import cache

        datos = cache.get(cls.CLAVE_CACHE)
        if datos is None:
            fila = cls.objects.filter(pk=1).first()
            q = settings.QUATTRETV
            if fila:
                datos = {
                    'cuota_minutos': fila.horas_por_cliente * 60,
                    'max_minutos': fila.horas_por_grabacion * 60,
                    # 12 meses son 365 dias, no 360.
                    'conservar_dias': round(fila.meses_conservar * 365 / 12),
                    'avisar_dias': fila.dias_aviso,
                }
            else:
                datos = {
                    'cuota_minutos': q.get('PVR_CUOTA_MINUTOS', 1800),
                    'max_minutos': q.get('PVR_MAX_MINUTOS', 180),
                    'conservar_dias': q.get('PVR_CONSERVAR_DIAS', 365),
                    'avisar_dias': q.get('PVR_AVISAR_DIAS', 7),
                }
            cache.set(cls.CLAVE_CACHE, datos, 300)
        return datos


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

    # Las grabaciones que se hicieron en Ministra se importan para que el
    # cliente no las pierda. Estas no se mandan nunca a ningun grabador: el
    # fichero ya existe, o lo esta haciendo Ministra.
    ministra_id = models.IntegerField(
        null=True, blank=True, unique=True,
        help_text='id de la grabacion en Ministra (tabla users_rec)'
    )

    # Options
    pre_padding = models.PositiveIntegerField(default=0, help_text='Minutes before start')
    post_padding = models.PositiveIntegerField(default=0, help_text='Minutes after end')

    class Meta:
        verbose_name = 'Recording'
        verbose_name_plural = 'Recordings'
        ordering = ['-start_time']
        indexes = [
            # dispatch_due_recordings recorre las pendientes cada minuto.
            models.Index(fields=['status', 'start_time']),
        ]

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

    @property
    def caduca(self):
        """Cuando se borra sola (ver AjustesGrabacion), o None si nunca."""
        from datetime import datetime, timedelta
        from django.conf import settings
        from django.utils import timezone

        dias = AjustesGrabacion.actual()['conservar_dias']
        if not dias:
            return None
        desde = settings.QUATTRETV.get('PVR_CONSERVAR_DESDE', '')
        base = self.end_time
        if desde:
            puesta = timezone.make_aware(datetime.strptime(desde, '%Y-%m-%d'))
            base = max(base, puesta)
        return base + timedelta(days=dias)


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
