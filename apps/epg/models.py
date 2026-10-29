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

    # Cuando empezo y acabo de verdad, segun la EIT de la propia emision (ver
    # apps/epg/eit.py). En pantalla se ve siempre la hora de la guia; esta
    # solo sirve para que el archivo arranque donde empieza el programa.
    inicio_real = models.DateTimeField(null=True, blank=True)
    fin_real = models.DateTimeField(null=True, blank=True)

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


class FilaSemana(models.Model):
    """
    Una fila de "Ultimos 7 dias" (peliculas, series...) y si se ofrece.

    Solo existen las que se han tocado desde el panel: una fila sin ficha se
    ve, que es lo normal.
    """
    grupo = models.CharField(max_length=20, unique=True)
    visible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.grupo} ({'visible' if self.visible else 'oculta'})"


class TituloSemana(models.Model):
    """
    Correccion a mano de un titulo de "Ultimos 7 dias".

    El tipo se adivina con la guia y a veces falla: una serie que sale como
    entretenimiento, una teletienda que se cuela. Aqui se le dice a que fila
    va, que no salga, o que caratula lleva. Vale para todas sus emisiones,
    tambien las de las semanas que vienen.
    """
    clave = models.CharField(max_length=300, unique=True,
                             help_text='Titulo en minusculas y sin acentos')
    titulo = models.CharField(max_length=500)
    grupo = models.CharField(max_length=20, blank=True,
                             help_text='Vacio: la que le toque sola')
    oculto = models.BooleanField(default=False)
    imagen = models.URLField(max_length=500, blank=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizado']

    def __str__(self):
        return self.titulo


class ProgresoArchivo(models.Model):
    """
    Por donde va cada aparato en lo que ha visto del archivo, para "Seguir
    viendo" del videoclub. Vale lo visto desde el videoclub y desde la guia.
    Se borra solo al acabarlo o cuando el archivo ya no lo tiene.
    """
    device = models.ForeignKey('devices.Device', on_delete=models.CASCADE,
                               related_name='progresos_archivo')
    channel = models.ForeignKey('channels.Channel', on_delete=models.CASCADE, related_name='+')
    inicio = models.DateTimeField(help_text='Inicio del programa en la guia')
    posicion = models.PositiveIntegerField(help_text='Segundos desde el inicio')
    duracion = models.PositiveIntegerField()
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('device', 'channel', 'inicio')
        ordering = ['-actualizado']

    def __str__(self):
        return f'{self.device_id} {self.channel_id} {self.inicio:%d/%m %H:%M} {self.posicion}s'


class ObservacionEit(models.Model):
    """
    Un cambio de programa visto en la EIT de la señal (ver apps/epg/eit.py):
    que empezo y cuando de verdad. Se guarda unos dias para volver a aplicarlo
    cuando la guia se recarga y para ver si una fuente va desviada.
    """
    channel = models.ForeignKey('channels.Channel', on_delete=models.CASCADE, related_name='+')
    inicio = models.DateTimeField(db_index=True)
    nombre = models.CharField(max_length=300)
    visto = models.DateTimeField()

    class Meta:
        unique_together = ('channel', 'inicio', 'nombre')
        ordering = ['-inicio']

    def __str__(self):
        return f'{self.channel_id} {self.inicio:%d/%m %H:%M:%S} {self.nombre}'


class FuenteCaratula(models.Model):
    """
    De donde se sacan las caratulas que la guia no trae (Configuracion del
    panel). Se prueban por orden, solo las activas; si una falla o no tiene la
    caratula, se pasa a la siguiente. Ver apps/stalker_api/caratulas.py.
    """
    TIPOS = [
        ('tmdb', 'TMDB'),
        ('tvmaze', 'TVmaze'),
        ('omdb', 'OMDb'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPOS, unique=True)
    activa = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)
    clave = models.CharField(max_length=300, blank=True)
    buscadas = models.PositiveIntegerField(default=0)
    encontradas = models.PositiveIntegerField(default=0)
    ultimo_error = models.CharField(max_length=300, blank=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return self.get_tipo_display()
