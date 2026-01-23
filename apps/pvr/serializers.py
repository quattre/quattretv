from rest_framework import serializers
from .models import Recording, RecordingRule


class RecordingSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    actual_start_time = serializers.ReadOnlyField()
    actual_end_time = serializers.ReadOnlyField()

    class Meta:
        model = Recording
        fields = [
            'id', 'user', 'channel', 'channel_name', 'program',
            'title', 'description', 'start_time', 'end_time',
            'status', 'error_message',
            'file_path', 'file_size', 'stream_url', 'duration',
            'pre_padding', 'post_padding',
            'actual_start_time', 'actual_end_time',
            'created_at'
        ]
        read_only_fields = ['user', 'status', 'file_path', 'file_size', 'stream_url', 'duration']


class RecordingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recording
        fields = [
            'channel', 'program', 'title', 'description',
            'start_time', 'end_time', 'pre_padding', 'post_padding'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class RecordingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingRule
        fields = [
            'id', 'name', 'is_active', 'channel', 'title_contains',
            'category', 'pre_padding', 'post_padding', 'keep_recordings'
        ]
        read_only_fields = ['user']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
