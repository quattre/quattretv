from rest_framework import serializers
from .models import TimeshiftArchive


class TimeshiftArchiveSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source='channel.name', read_only=True)

    class Meta:
        model = TimeshiftArchive
        fields = [
            'id', 'channel', 'channel_name', 'start_time', 'end_time',
            'stream_url', 'duration'
        ]
