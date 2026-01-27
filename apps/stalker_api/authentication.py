"""
MAC-based authentication for STB devices.
"""
import re
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from apps.devices.models import Device


class MACAuthentication(BaseAuthentication):
    """
    Authenticate STB devices by MAC address.
    MAC can be in Cookie header or query params.
    """

    def authenticate(self, request):
        mac_address = self.get_mac_from_request(request)
        if not mac_address:
            return None

        try:
            device = Device.objects.select_related('user').get(
                mac_address=mac_address,
                is_active=True
            )
        except Device.DoesNotExist:
            raise AuthenticationFailed('Device not registered')

        if not device.user.is_active:
            raise AuthenticationFailed('User account is disabled')

        if not device.user.is_subscription_active:
            raise AuthenticationFailed('Subscription expired')

        # Update device activity
        device.update_activity(
            ip_address=self.get_client_ip(request)
        )

        return (device.user, device)

    def get_mac_from_request(self, request):
        """Extract MAC address from request."""
        # Try Cookie header first (standard Stalker format)
        cookie_mac = request.COOKIES.get('mac')
        if cookie_mac:
            return self.normalize_mac(cookie_mac)

        # Try query parameter
        query_mac = request.query_params.get('mac') if hasattr(request, 'query_params') else request.GET.get('mac')
        if query_mac:
            return self.normalize_mac(query_mac)

        # Try Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('MAC '):
            return self.normalize_mac(auth_header[4:])

        return None

    @staticmethod
    def normalize_mac(mac):
        """Normalize MAC address to XX:XX:XX:XX:XX:XX format."""
        if not mac:
            return None

        # Remove common prefixes
        mac = mac.replace('mac=', '').strip()

        # URL decode if needed
        mac = mac.replace('%3A', ':')

        # Remove all separators and convert to uppercase
        mac = re.sub(r'[^A-Fa-f0-9]', '', mac).upper()

        if len(mac) != 12:
            return None

        # Format with colons
        return ':'.join(mac[i:i+2] for i in range(0, 12, 2))

    @staticmethod
    def get_client_ip(request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
