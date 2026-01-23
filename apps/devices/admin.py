from django.contrib import admin
from .models import Device, DeviceMessage


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'mac_address', 'user', 'device_type', 'name',
        'is_active', 'is_online', 'last_seen', 'last_ip'
    )
    list_filter = ('device_type', 'is_active', 'last_seen')
    search_fields = ('mac_address', 'serial_number', 'user__username', 'name')
    readonly_fields = ('token', 'token_expires', 'last_seen', 'created_at', 'updated_at')

    fieldsets = (
        ('Device Info', {
            'fields': ('user', 'mac_address', 'serial_number', 'device_type', 'name', 'model', 'firmware_version')
        }),
        ('Authentication', {
            'fields': ('token', 'token_expires', 'is_active')
        }),
        ('Status', {
            'fields': ('last_seen', 'last_ip', 'last_channel')
        }),
        ('Settings', {
            'fields': ('timezone', 'language', 'volume', 'brightness')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DeviceMessage)
class DeviceMessageAdmin(admin.ModelAdmin):
    list_display = ('title', 'device', 'user', 'message_type', 'is_read', 'created_at')
    list_filter = ('message_type', 'is_read', 'created_at')
    search_fields = ('title', 'message')
