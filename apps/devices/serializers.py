from rest_framework import serializers
from .models import Device, DeviceMessage


class DeviceSerializer(serializers.ModelSerializer):
    is_online = serializers.ReadOnlyField()
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Device
        fields = [
            'id', 'user', 'user_username', 'mac_address', 'serial_number',
            'device_type', 'name', 'model', 'firmware_version',
            'is_active', 'last_seen', 'last_ip', 'is_online',
            'timezone', 'language', 'created_at'
        ]
        read_only_fields = ['id', 'token', 'last_seen', 'last_ip']


class DeviceRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for device self-registration."""
    class Meta:
        model = Device
        fields = ['mac_address', 'serial_number', 'device_type', 'model', 'firmware_version']


class DeviceMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceMessage
        fields = [
            'id', 'device', 'user', 'title', 'message',
            'message_type', 'expires_at', 'is_read', 'created_at'
        ]
