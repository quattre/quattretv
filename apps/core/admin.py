from django.contrib import admin
from .models import ServerSettings


@admin.register(ServerSettings)
class ServerSettingsAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'updated_at')
    search_fields = ('key', 'description')
    readonly_fields = ('created_at', 'updated_at')
