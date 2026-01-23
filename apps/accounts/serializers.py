from rest_framework import serializers
from .models import User, Tariff, UserSession


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = [
            'id', 'name', 'description', 'price', 'duration_days',
            'max_devices', 'max_concurrent_streams',
            'has_timeshift', 'has_pvr', 'has_vod', 'has_catchup',
            'is_active'
        ]


class UserSerializer(serializers.ModelSerializer):
    tariff = TariffSerializer(read_only=True)
    is_subscription_active = serializers.ReadOnlyField()
    active_devices_count = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'tariff', 'subscription_expires', 'balance',
            'max_devices', 'max_concurrent_streams',
            'is_subscription_active', 'active_devices_count'
        ]
        read_only_fields = ['id', 'username']


class UserSessionSerializer(serializers.ModelSerializer):
    duration = serializers.ReadOnlyField()

    class Meta:
        model = UserSession
        fields = [
            'id', 'user', 'device', 'channel', 'ip_address',
            'started_at', 'ended_at', 'is_active', 'duration'
        ]
