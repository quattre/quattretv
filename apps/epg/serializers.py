from rest_framework import serializers
from .models import EpgSource, Program


class EpgSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EpgSource
        fields = [
            'id', 'name', 'url', 'is_active',
            'last_update', 'update_interval', 'auto_update'
        ]


class ProgramSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    channel_number = serializers.IntegerField(source='channel.number', read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    progress_percent = serializers.ReadOnlyField()

    class Meta:
        model = Program
        fields = [
            'id', 'channel', 'channel_name', 'channel_number',
            'title', 'description', 'start_time', 'end_time',
            'category', 'episode_title', 'season', 'episode',
            'year', 'rating', 'poster', 'icon',
            'is_live', 'is_new', 'is_premiere', 'has_subtitles',
            'duration_minutes', 'is_current', 'progress_percent'
        ]


class ProgramCompactSerializer(serializers.ModelSerializer):
    """Compact serializer for EPG lists."""
    class Meta:
        model = Program
        fields = [
            'id', 'channel', 'title', 'start_time', 'end_time',
            'category', 'is_current', 'progress_percent'
        ]
