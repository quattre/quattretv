from rest_framework import serializers
from .models import Category, Channel, ChannelPackage, ChannelStream, Favorite


class CategorySerializer(serializers.ModelSerializer):
    channels_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'alias', 'description', 'icon',
            'parent', 'order', 'is_adult', 'is_active', 'channels_count'
        ]

    def get_channels_count(self, obj):
        return obj.channels.filter(is_active=True).count()


class ChannelStreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelStream
        fields = ['id', 'name', 'url', 'stream_type', 'quality', 'priority']


class ChannelListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for channel lists."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    logo_display_url = serializers.ReadOnlyField()

    class Meta:
        model = Channel
        fields = [
            'id', 'name', 'number', 'logo_display_url',
            'category', 'category_name',
            'is_hd', 'is_4k', 'is_adult',
            'has_epg', 'has_timeshift', 'has_catchup'
        ]


class ChannelDetailSerializer(serializers.ModelSerializer):
    """Full channel details with streams."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    logo_display_url = serializers.ReadOnlyField()
    streams = ChannelStreamSerializer(many=True, read_only=True)

    class Meta:
        model = Channel
        fields = [
            'id', 'name', 'number', 'logo', 'logo_url', 'logo_display_url',
            'category', 'category_name', 'description',
            'stream_url', 'stream_type', 'backup_stream_url',
            'has_epg', 'has_timeshift', 'has_catchup', 'has_recording',
            'is_hd', 'is_4k', 'is_adult',
            'epg_id', 'timeshift_hours',
            'country', 'language',
            'streams', 'is_active'
        ]


class ChannelPackageSerializer(serializers.ModelSerializer):
    channels_count = serializers.SerializerMethodField()

    class Meta:
        model = ChannelPackage
        fields = ['id', 'name', 'description', 'is_active', 'channels_count']

    def get_channels_count(self, obj):
        return obj.channels.filter(is_active=True).count()


class FavoriteSerializer(serializers.ModelSerializer):
    channel = ChannelListSerializer(read_only=True)
    channel_id = serializers.PrimaryKeyRelatedField(
        queryset=Channel.objects.filter(is_active=True),
        source='channel',
        write_only=True
    )

    class Meta:
        model = Favorite
        fields = ['id', 'channel', 'channel_id', 'order', 'created_at']
