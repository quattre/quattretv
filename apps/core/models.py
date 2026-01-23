"""
Core models - Base classes and utilities.
"""
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base model with created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ActiveManager(models.Manager):
    """Manager that returns only active objects."""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class ActivableModel(models.Model):
    """Abstract base model with active status."""
    is_active = models.BooleanField(default=True, db_index=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        abstract = True


class ServerSettings(TimeStampedModel):
    """Global server settings stored in database."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Server Setting'
        verbose_name_plural = 'Server Settings'

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value, description=''):
        obj, _ = cls.objects.update_or_create(
            key=key,
            defaults={'value': value, 'description': description}
        )
        return obj
