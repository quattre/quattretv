"""
User and subscription models.
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from apps.core.models import TimeStampedModel


class User(AbstractUser):
    """Custom user model for IPTV subscribers."""
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Subscription info
    tariff = models.ForeignKey(
        'Tariff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    subscription_expires = models.DateTimeField(null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Limits
    max_devices = models.PositiveIntegerField(default=5)
    max_concurrent_streams = models.PositiveIntegerField(default=2)

    # Parental control
    parental_password = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username

    @property
    def is_subscription_active(self):
        # Si no tiene fecha de expiración, nunca caduca (siempre activo)
        if not self.subscription_expires:
            return True
        return self.subscription_expires > timezone.now()

    @property
    def active_devices_count(self):
        return self.devices.filter(is_active=True).count()


class Tariff(TimeStampedModel):
    """Subscription tariff/plan."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(default=30)

    # Features
    max_devices = models.PositiveIntegerField(default=5)
    max_concurrent_streams = models.PositiveIntegerField(default=2)
    has_timeshift = models.BooleanField(default=True)
    has_pvr = models.BooleanField(default=True)
    has_vod = models.BooleanField(default=True)
    has_catchup = models.BooleanField(default=True)

    # Channel packages (grupos de canales)
    channel_packages = models.ManyToManyField(
        'channels.ChannelPackage',
        blank=True,
        related_name='tariffs'
    )

    # Canales individuales seleccionados
    channels = models.ManyToManyField(
        'channels.Channel',
        blank=True,
        related_name='tariffs',
        help_text='Canales individuales incluidos en esta tarifa'
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tariff'
        verbose_name_plural = 'Tariffs'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserSession(TimeStampedModel):
    """Track user streaming sessions."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    device = models.ForeignKey(
        'devices.Device',
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions'
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} - {self.device.mac_address}"

    @property
    def duration(self):
        end = self.ended_at or timezone.now()
        return end - self.started_at
