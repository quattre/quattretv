from django.contrib import admin
from .models import Category, Channel, ChannelPackage, ChannelStream, Favorite


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'alias', 'parent', 'order', 'is_adult', 'is_active')
    list_filter = ('is_active', 'is_adult', 'parent')
    search_fields = ('name', 'alias')
    prepopulated_fields = {'alias': ('name',)}
    ordering = ('order', 'name')


class ChannelStreamInline(admin.TabularInline):
    model = ChannelStream
    extra = 1


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = (
        'number', 'name', 'category', 'is_hd', 'is_4k',
        'has_epg', 'has_timeshift', 'is_active'
    )
    list_filter = ('category', 'is_active', 'is_hd', 'is_4k', 'is_adult', 'has_epg', 'has_timeshift')
    search_fields = ('name', 'number', 'epg_id')
    filter_horizontal = ('packages',)
    inlines = [ChannelStreamInline]
    ordering = ('number',)

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'number', 'category', 'description')
        }),
        ('Logo', {
            'fields': ('logo', 'logo_url')
        }),
        ('Streaming', {
            'fields': ('stream_url', 'stream_type', 'backup_stream_url')
        }),
        ('Features', {
            'fields': (
                'has_epg', 'has_timeshift', 'has_catchup', 'has_recording',
                'is_hd', 'is_4k', 'is_adult'
            )
        }),
        ('EPG & Timeshift', {
            'fields': ('epg_id', 'timeshift_hours')
        }),
        ('Packages & Metadata', {
            'fields': ('packages', 'country', 'language', 'is_active')
        }),
    )


@admin.register(ChannelPackage)
class ChannelPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'channel', 'order', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'channel__name')
