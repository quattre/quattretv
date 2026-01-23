from django.contrib import admin
from .models import VodCategory, Movie, Series, Season, Episode, WatchHistory


@admin.register(VodCategory)
class VodCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'alias', 'parent', 'order', 'is_adult', 'is_active')
    list_filter = ('is_active', 'is_adult', 'parent')
    prepopulated_fields = {'alias': ('name',)}


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'rating', 'category', 'is_hd', 'is_4k', 'is_featured', 'is_active')
    list_filter = ('category', 'is_active', 'is_hd', 'is_4k', 'is_adult', 'is_featured', 'year')
    search_fields = ('title', 'original_title', 'director', 'cast')


class SeasonInline(admin.TabularInline):
    model = Season
    extra = 1


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ('title', 'year_start', 'year_end', 'rating', 'category', 'is_featured', 'is_active')
    list_filter = ('category', 'is_active', 'is_adult', 'is_featured')
    search_fields = ('title', 'original_title', 'cast')
    inlines = [SeasonInline]


class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 1


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('series', 'number', 'title')
    list_filter = ('series',)
    inlines = [EpisodeInline]


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('title', 'season', 'number', 'duration', 'air_date', 'is_active')
    list_filter = ('season__series', 'is_active')
    search_fields = ('title',)


@admin.register(WatchHistory)
class WatchHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'movie', 'episode', 'position', 'completed', 'watched_at')
    list_filter = ('completed', 'watched_at')
    search_fields = ('user__username',)
