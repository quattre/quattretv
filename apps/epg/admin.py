from django.contrib import admin
from .models import EpgSource, Program


@admin.register(EpgSource)
class EpgSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'is_active', 'last_update', 'auto_update')
    list_filter = ('is_active', 'auto_update')
    search_fields = ('name', 'url')
    readonly_fields = ('last_update',)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel', 'start_time', 'end_time', 'category', 'is_current')
    list_filter = ('category', 'start_time', 'channel')
    search_fields = ('title', 'description')
    date_hierarchy = 'start_time'
    raw_id_fields = ('channel',)
