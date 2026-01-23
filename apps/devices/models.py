"""
Device/STB models.
"""
import secrets
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel, ActivableModel


class DeviceType(models.TextChoices):
    MAG = 'mag', 'MAG STB'
    ANDROID = 'android', 'Android'
    IOS = 'ios', 'iOS'
    SMART_TV = 'smart_tv', 'Smart TV'
    WEB = 'web', 'Web Browser'
    OTHER = 'other', 'Other'


class Device(TimeStampedModel, ActivableModel):
    """Registered device/STB."""
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='devices'
    )
    mac_address = models.CharField(
        max_length=17,
        unique=True,
        db_index=True,
        help_text='Format: XX:XX:XX:XX:XX:XX'
    )
    serial_number = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.MAG
    )
    name = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)

    # Authentication
    token = models.CharField(max_length=64, unique=True, blank=True)
    token_expires = models.DateTimeField(null=True, blank=True)

    # Status
    last_seen = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='last_watched_by'
    )

    # Settings
    timezone = models.CharField(max_length=50, default='Europe/Madrid')
    language = models.CharField(max_length=5, default='es')
    volume = models.PositiveIntegerField(default=50)
    brightness = models.PositiveIntegerField(default=100)

    class Meta:
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.mac_address} ({self.user.username})"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        # Normalize MAC address
        self.mac_address = self.mac_address.upper().replace('-', ':')
        super().save(*args, **kwargs)

    @staticmethod
    def generate_token():
        return secrets.token_hex(32)

    def refresh_token(self, hours=24):
        """Generate new token with expiration."""
        self.token = self.generate_token()
        self.token_expires = timezone.now() + timezone.timedelta(hours=hours)
        self.save(update_fields=['token', 'token_expires'])
        return self.token

    def update_activity(self, ip_address=None, channel=None):
        """Update last seen timestamp."""
        self.last_seen = timezone.now()
        if ip_address:
            self.last_ip = ip_address
        if channel:
            self.last_channel = channel
        self.save(update_fields=['last_seen', 'last_ip', 'last_channel'])

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        threshold = timezone.now() - timezone.timedelta(minutes=5)
        return self.last_seen > threshold


class DeviceMessage(TimeStampedModel):
    """Messages to be sent to devices."""
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True,
        help_text='Leave empty to send to all devices'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='device_messages',
        null=True,
        blank=True,
        help_text='Send to all devices of this user'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('info', 'Information'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('reload', 'Reload Portal'),
        ],
        default='info'
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Device Message'
        verbose_name_plural = 'Device Messages'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.device or 'All devices'}"
