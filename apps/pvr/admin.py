from django.contrib import admin
from .models import Recording, RecordingRule, StorageServer


@admin.register(StorageServer)
class StorageServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'api_url', 'is_active', 'last_sync')
    list_filter = ('role', 'is_active')
    search_fields = ('name', 'api_url')
    readonly_fields = ('last_sync',)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'channel', 'start_time', 'status', 'created_at')
    list_filter = ('status', 'channel', 'start_time')
    search_fields = ('title', 'user__username')
    date_hierarchy = 'start_time'
    raw_id_fields = ('user', 'channel', 'program')


@admin.register(RecordingRule)
class RecordingRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'channel', 'title_contains', 'is_active')
    list_filter = ('is_active', 'channel')
    search_fields = ('name', 'user__username', 'title_contains')
