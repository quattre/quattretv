from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint."""
    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([AllowAny])
def server_info(request):
    """Server information endpoint."""
    return Response({
        'name': 'QuattreTV',
        'version': '1.0.0',
        'api_version': 'v1',
        'timeshift_enabled': settings.QUATTRETV['TIMESHIFT_ENABLED'],
        'timeshift_hours': settings.QUATTRETV['TIMESHIFT_HOURS'],
    })
