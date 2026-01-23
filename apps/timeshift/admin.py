from django.contrib import admin
from .models import TimeshiftArchive


@admin.register(TimeshiftArchive)
class TimeshiftArchiveAdmin(admin.ModelAdmin):
    list_display = ('channel', 'start_time', 'end_time', 'duration')
    list_filter = ('channel', 'start_time')
    search_fields = ('channel__name',)
    date_hierarchy = 'start_time'
