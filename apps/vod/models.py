"""
Video On Demand models.
"""
from django.db import models
from apps.core.models import TimeStampedModel, ActivableModel


class VodCategory(TimeStampedModel, ActivableModel):
    """VOD Category."""
    name = models.CharField(max_length=100)
    alias = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='vod/categories/', blank=True, null=True)
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
        verbose_name = 'VOD Category'
        verbose_name_plural = 'VOD Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Movie(TimeStampedModel, ActivableModel):
    """Movie/Film."""
    title = models.CharField(max_length=300)
    original_title = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True, help_text='Duration in minutes')
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    imdb_id = models.CharField(max_length=20, blank=True)
    tmdb_id = models.CharField(max_length=20, blank=True)

    # Media
    poster = models.ImageField(upload_to='vod/posters/', blank=True, null=True)
    poster_url = models.URLField(max_length=500, blank=True)
    backdrop = models.ImageField(upload_to='vod/backdrops/', blank=True, null=True)
    backdrop_url = models.URLField(max_length=500, blank=True)
    trailer_url = models.URLField(max_length=500, blank=True)

    # Stream
    stream_url = models.URLField(max_length=500)
    stream_type = models.CharField(
        max_length=10,
        choices=[
            ('hls', 'HLS'),
            ('dash', 'DASH'),
            ('mp4', 'MP4'),
        ],
        default='hls'
    )

    # Categorization
    category = models.ForeignKey(
        VodCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movies'
    )
    genres = models.CharField(max_length=200, blank=True, help_text='Comma-separated')
    director = models.CharField(max_length=200, blank=True)
    cast = models.TextField(blank=True, help_text='Comma-separated')
    country = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=50, blank=True)

    # Flags
    is_hd = models.BooleanField(default=False)
    is_4k = models.BooleanField(default=False)
    is_adult = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Movie'
        verbose_name_plural = 'Movies'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.year})"


class Series(TimeStampedModel, ActivableModel):
    """TV Series."""
    title = models.CharField(max_length=300)
    original_title = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    year_start = models.PositiveIntegerField(null=True, blank=True)
    year_end = models.PositiveIntegerField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    imdb_id = models.CharField(max_length=20, blank=True)
    tmdb_id = models.CharField(max_length=20, blank=True)

    # Media
    poster = models.ImageField(upload_to='vod/series/posters/', blank=True, null=True)
    poster_url = models.URLField(max_length=500, blank=True)
    backdrop = models.ImageField(upload_to='vod/series/backdrops/', blank=True, null=True)
    backdrop_url = models.URLField(max_length=500, blank=True)

    # Categorization
    category = models.ForeignKey(
        VodCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='series'
    )
    genres = models.CharField(max_length=200, blank=True)
    cast = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Flags
    is_adult = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Series'
        verbose_name_plural = 'Series'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Season(TimeStampedModel):
    """Season of a TV Series."""
    series = models.ForeignKey(
        Series,
        on_delete=models.CASCADE,
        related_name='seasons'
    )
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    poster = models.ImageField(upload_to='vod/seasons/', blank=True, null=True)
    poster_url = models.URLField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Season'
        verbose_name_plural = 'Seasons'
        ordering = ['number']
        unique_together = ['series', 'number']

    def __str__(self):
        return f"{self.series.title} - Season {self.number}"


class Episode(TimeStampedModel, ActivableModel):
    """Episode of a TV Series."""
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name='episodes'
    )
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True)
    air_date = models.DateField(null=True, blank=True)

    # Media
    poster = models.ImageField(upload_to='vod/episodes/', blank=True, null=True)
    poster_url = models.URLField(max_length=500, blank=True)

    # Stream
    stream_url = models.URLField(max_length=500)
    stream_type = models.CharField(max_length=10, default='hls')

    class Meta:
        verbose_name = 'Episode'
        verbose_name_plural = 'Episodes'
        ordering = ['number']
        unique_together = ['season', 'number']

    def __str__(self):
        return f"{self.season.series.title} S{self.season.number:02d}E{self.number:02d} - {self.title}"


class WatchHistory(TimeStampedModel):
    """User watch history for VOD."""
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='watch_history'
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='watch_history'
    )
    episode = models.ForeignKey(
        Episode,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='watch_history'
    )
    position = models.PositiveIntegerField(default=0, help_text='Position in seconds')
    completed = models.BooleanField(default=False)
    watched_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Watch History'
        verbose_name_plural = 'Watch History'
        ordering = ['-watched_at']

    def __str__(self):
        content = self.movie or self.episode
        return f"{self.user.username} - {content}"
