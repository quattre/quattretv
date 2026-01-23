from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Tariff, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'tariff', 'subscription_expires',
        'is_subscription_active', 'active_devices_count', 'is_active'
    )
    list_filter = ('is_active', 'is_staff', 'tariff')
    search_fields = ('username', 'email', 'first_name', 'last_name')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Subscription', {
            'fields': ('tariff', 'subscription_expires', 'balance')
        }),
        ('Limits', {
            'fields': ('max_devices', 'max_concurrent_streams')
        }),
        ('Contact', {
            'fields': ('phone', 'address', 'notes')
        }),
        ('Parental Control', {
            'fields': ('parental_password',)
        }),
    )


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'price', 'duration_days', 'max_devices',
        'has_timeshift', 'has_pvr', 'has_vod', 'is_active'
    )
    list_filter = ('is_active', 'has_timeshift', 'has_pvr', 'has_vod')
    filter_horizontal = ('channel_packages',)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'device', 'channel', 'ip_address',
        'started_at', 'is_active'
    )
    list_filter = ('is_active', 'started_at')
    search_fields = ('user__username', 'device__mac_address', 'ip_address')
    readonly_fields = ('started_at',)
