from rest_framework import serializers
from .models import VodCategory, Movie, Series, Season, Episode, WatchHistory


class VodCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VodCategory
        fields = ['id', 'name', 'alias', 'description', 'icon', 'parent', 'order', 'is_adult']


class MovieListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Movie
        fields = [
            'id', 'title', 'year', 'rating', 'duration',
            'poster', 'poster_url', 'category', 'category_name',
            'is_hd', 'is_4k', 'is_featured'
        ]


class MovieDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'


class EpisodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Episode
        fields = [
            'id', 'number', 'title', 'description', 'duration',
            'air_date', 'poster', 'poster_url', 'stream_url', 'stream_type'
        ]


class SeasonSerializer(serializers.ModelSerializer):
    episodes = EpisodeSerializer(many=True, read_only=True)
    episodes_count = serializers.SerializerMethodField()

    class Meta:
        model = Season
        fields = ['id', 'number', 'title', 'description', 'poster', 'poster_url', 'episodes', 'episodes_count']

    def get_episodes_count(self, obj):
        return obj.episodes.filter(is_active=True).count()


class SeriesListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    seasons_count = serializers.SerializerMethodField()

    class Meta:
        model = Series
        fields = [
            'id', 'title', 'year_start', 'year_end', 'rating',
            'poster', 'poster_url', 'category', 'category_name',
            'is_featured', 'seasons_count'
        ]

    def get_seasons_count(self, obj):
        return obj.seasons.count()


class SeriesDetailSerializer(serializers.ModelSerializer):
    seasons = SeasonSerializer(many=True, read_only=True)

    class Meta:
        model = Series
        fields = '__all__'


class WatchHistorySerializer(serializers.ModelSerializer):
    movie = MovieListSerializer(read_only=True)
    episode = EpisodeSerializer(read_only=True)

    class Meta:
        model = WatchHistory
        fields = ['id', 'movie', 'episode', 'position', 'completed', 'watched_at']
