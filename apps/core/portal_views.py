"""
Portal admin views for QuattreTV.
"""
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Q

from apps.accounts.models import User, Tariff
from apps.devices.models import Device
from apps.channels.models import Channel, Category, ChannelStream


def get_base_stats():
    """Get base statistics for sidebar."""
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    return {
        'users_count': User.objects.count(),
        'devices_online': Device.objects.filter(last_seen__gte=online_threshold).count(),
        'channels_count': Channel.objects.filter(is_active=True).count(),
    }


@staff_member_required
def dashboard(request):
    """Main dashboard view."""
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    # Statistics
    stats = {
        'users_count': User.objects.count(),
        'users_active': User.objects.filter(
            subscription_expires__gte=now
        ).count(),
        'devices_count': Device.objects.count(),
        'devices_online': Device.objects.filter(
            last_seen__gte=online_threshold
        ).count(),
        'channels_count': Channel.objects.filter(is_active=True).count(),
        'categories_count': Category.objects.count(),
        'streams_active': Device.objects.filter(
            last_seen__gte=online_threshold
        ).count(),
    }

    # Recent users
    recent_users = User.objects.select_related('tariff').order_by('-date_joined')[:5]

    # Online devices
    online_devices = Device.objects.filter(
        last_seen__gte=online_threshold
    ).select_related('user').order_by('-last_seen')[:5]

    # Top channels
    top_channels = Channel.objects.filter(
        is_active=True
    ).select_related('category').order_by('number')[:10]

    # Chart data (mock for now - last 24 hours)
    chart_labels = [f'{i}:00' for i in range(24)]
    chart_data = [0] * 24  # Would be real connection data

    # Device types
    device_types = Device.objects.values('device_type').annotate(count=Count('id'))
    device_types_labels = [d['device_type'].upper() for d in device_types]
    device_types_data = [d['count'] for d in device_types]

    context = {
        'active_page': 'dashboard',
        'stats': stats,
        'recent_users': recent_users,
        'online_devices': online_devices,
        'top_channels': top_channels,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'device_types_labels': json.dumps(device_types_labels if device_types_labels else ['Sin datos']),
        'device_types_data': json.dumps(device_types_data if device_types_data else [1]),
    }
    context['stats'].update(get_base_stats())

    return render(request, 'portal/pages/dashboard.html', context)


@staff_member_required
def users_list(request):
    """Users list view."""
    users = User.objects.select_related('tariff').prefetch_related('devices')

    # Filters
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search)
        )

    tariff_id = request.GET.get('tariff')
    if tariff_id:
        users = users.filter(tariff_id=tariff_id)

    status = request.GET.get('status')
    if status == 'active':
        users = users.filter(subscription_expires__gte=timezone.now())
    elif status == 'inactive':
        users = users.filter(is_active=False)
    elif status == 'expired':
        users = users.filter(subscription_expires__lt=timezone.now())

    users = users.order_by('-date_joined')

    # Pagination
    paginator = Paginator(users, 25)
    page = request.GET.get('page', 1)
    users = paginator.get_page(page)

    context = {
        'active_page': 'users',
        'stats': get_base_stats(),
        'users': users,
        'tariffs': Tariff.objects.filter(is_active=True),
    }

    return render(request, 'portal/pages/users.html', context)


@staff_member_required
def user_create(request):
    """Create new user."""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        tariff_id = request.POST.get('tariff')
        duration = int(request.POST.get('duration', 30))
        max_devices = int(request.POST.get('max_devices', 5))

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El usuario ya existe')
            return redirect('portal:users')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            max_devices=max_devices,
        )

        if tariff_id:
            user.tariff_id = tariff_id
            user.subscription_expires = timezone.now() + timedelta(days=duration)
            user.save()

        messages.success(request, f'Usuario {username} creado correctamente')

    return redirect('portal:users')


@staff_member_required
def user_edit(request, user_id):
    """Edit user view."""
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        user.email = request.POST.get('email', '')
        user.tariff_id = request.POST.get('tariff') or None
        user.max_devices = int(request.POST.get('max_devices', 5))
        user.is_active = 'is_active' in request.POST
        user.save()
        messages.success(request, 'Usuario actualizado')
        return redirect('portal:users')

    context = {
        'active_page': 'users',
        'stats': get_base_stats(),
        'edit_user': user,
        'tariffs': Tariff.objects.filter(is_active=True),
    }

    return render(request, 'portal/pages/user_edit.html', context)


@staff_member_required
def user_renew(request, user_id):
    """Renew user subscription."""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        days = int(request.POST.get('days', 30))

        if user.subscription_expires and user.subscription_expires > timezone.now():
            user.subscription_expires += timedelta(days=days)
        else:
            user.subscription_expires = timezone.now() + timedelta(days=days)

        user.save()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def user_delete(request, user_id):
    """Delete user."""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        username = user.username
        user.delete()
        messages.success(request, f'Usuario {username} eliminado')
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def user_devices(request, user_id):
    """View user devices."""
    user = get_object_or_404(User, id=user_id)
    devices = user.devices.all()

    context = {
        'active_page': 'users',
        'stats': get_base_stats(),
        'view_user': user,
        'devices': devices,
    }

    return render(request, 'portal/pages/user_devices.html', context)


# Devices views
@staff_member_required
def devices_list(request):
    """Devices list view."""
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    devices = Device.objects.select_related('user')

    # Stats
    stats = {
        'total': devices.count(),
        'online': devices.filter(last_seen__gte=online_threshold).count(),
        'mag': devices.filter(device_type='mag').count(),
        'apps': devices.filter(device_type__in=['android', 'ios']).count(),
    }

    # Filters
    search = request.GET.get('search')
    if search:
        devices = devices.filter(
            Q(mac_address__icontains=search) |
            Q(user__username__icontains=search) |
            Q(name__icontains=search)
        )

    device_type = request.GET.get('type')
    if device_type:
        devices = devices.filter(device_type=device_type)

    status = request.GET.get('status')
    if status == 'online':
        devices = devices.filter(last_seen__gte=online_threshold)
    elif status == 'offline':
        devices = devices.exclude(last_seen__gte=online_threshold)

    devices = devices.order_by('-last_seen')

    context = {
        'active_page': 'devices',
        'stats': {**get_base_stats(), **stats},
        'devices': devices,
        'all_users': User.objects.all(),
    }

    return render(request, 'portal/pages/devices.html', context)


@staff_member_required
def device_create(request):
    """Create new device."""
    if request.method == 'POST':
        mac_address = request.POST.get('mac_address', '').upper().replace('-', ':')
        user_id = request.POST.get('user')
        device_type = request.POST.get('device_type', 'mag')
        name = request.POST.get('name', '')

        if Device.objects.filter(mac_address=mac_address).exists():
            messages.error(request, 'Este MAC ya está registrado')
            return redirect('portal:devices')

        Device.objects.create(
            mac_address=mac_address,
            user_id=user_id,
            device_type=device_type,
            name=name,
        )

        messages.success(request, f'Dispositivo {mac_address} creado')

    return redirect('portal:devices')


@staff_member_required
def device_edit(request, device_id):
    """Edit device."""
    device = get_object_or_404(Device, id=device_id)

    if request.method == 'POST':
        device.name = request.POST.get('name', '')
        device.device_type = request.POST.get('device_type', 'mag')
        device.user_id = request.POST.get('user')
        device.is_active = 'is_active' in request.POST
        device.save()
        messages.success(request, 'Dispositivo actualizado')
        return redirect('portal:devices')

    context = {
        'active_page': 'devices',
        'stats': get_base_stats(),
        'device': device,
        'all_users': User.objects.all(),
    }

    return render(request, 'portal/pages/device_edit.html', context)


@staff_member_required
def device_refresh_token(request, device_id):
    """Refresh device token."""
    if request.method == 'POST':
        device = get_object_or_404(Device, id=device_id)
        device.refresh_token()
        return JsonResponse({'status': 'ok', 'token': device.token})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def device_delete(request, device_id):
    """Delete device."""
    if request.method == 'POST':
        device = get_object_or_404(Device, id=device_id)
        device.delete()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


# Channels views
@staff_member_required
def channels_list(request):
    """Channels list view."""
    channels = Channel.objects.select_related('category').prefetch_related('streams')

    # Filters
    search = request.GET.get('search')
    if search:
        channels = channels.filter(name__icontains=search)

    category_id = request.GET.get('category')
    if category_id:
        channels = channels.filter(category_id=category_id)

    status = request.GET.get('status')
    if status == 'active':
        channels = channels.filter(is_active=True)
    elif status == 'inactive':
        channels = channels.filter(is_active=False)

    channels = channels.order_by('number')

    context = {
        'active_page': 'channels',
        'stats': get_base_stats(),
        'channels': channels,
        'categories': Category.objects.all(),
    }

    return render(request, 'portal/pages/channels.html', context)


@staff_member_required
def channel_create(request):
    """Create new channel."""
    if request.method == 'POST':
        name = request.POST.get('name')
        number = int(request.POST.get('number', 0))
        category_id = request.POST.get('category') or None
        stream_url = request.POST.get('stream_url')
        logo = request.POST.get('logo', '')
        epg_channel_id = request.POST.get('epg_channel_id', '')
        is_hd = 'is_hd' in request.POST
        is_adult = 'is_adult' in request.POST
        has_archive = 'has_archive' in request.POST

        channel = Channel.objects.create(
            name=name,
            number=number,
            category_id=category_id,
            logo=logo,
            epg_channel_id=epg_channel_id,
            is_hd=is_hd,
            is_adult=is_adult,
            has_archive=has_archive,
        )

        if stream_url:
            ChannelStream.objects.create(
                channel=channel,
                url=stream_url,
                is_primary=True,
            )

        messages.success(request, f'Canal {name} creado')

    return redirect('portal:channels')


@staff_member_required
def channel_edit(request, channel_id):
    """Edit channel."""
    channel = get_object_or_404(Channel, id=channel_id)

    if request.method == 'POST':
        channel.name = request.POST.get('name')
        channel.number = int(request.POST.get('number', 0))
        channel.category_id = request.POST.get('category') or None
        channel.logo = request.POST.get('logo', '')
        channel.epg_channel_id = request.POST.get('epg_channel_id', '')
        channel.is_hd = 'is_hd' in request.POST
        channel.is_adult = 'is_adult' in request.POST
        channel.has_archive = 'has_archive' in request.POST
        channel.is_active = 'is_active' in request.POST
        channel.save()

        # Update stream
        stream_url = request.POST.get('stream_url')
        if stream_url:
            stream, created = ChannelStream.objects.get_or_create(
                channel=channel,
                is_primary=True,
                defaults={'url': stream_url}
            )
            if not created:
                stream.url = stream_url
                stream.save()

        messages.success(request, 'Canal actualizado')
        return redirect('portal:channels')

    context = {
        'active_page': 'channels',
        'stats': get_base_stats(),
        'channel': channel,
        'categories': Category.objects.all(),
    }

    return render(request, 'portal/pages/channel_edit.html', context)


@staff_member_required
def channel_delete(request, channel_id):
    """Delete channel."""
    if request.method == 'POST':
        channel = get_object_or_404(Channel, id=channel_id)
        channel.delete()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def channels_import(request):
    """Import channels from M3U."""
    if request.method == 'POST':
        # TODO: Implement M3U import
        messages.info(request, 'Función de importación M3U en desarrollo')

    return redirect('portal:channels')


# Categories
@staff_member_required
def categories_list(request):
    """Categories list."""
    categories = Category.objects.annotate(channels_count=Count('channels'))

    context = {
        'active_page': 'categories',
        'stats': get_base_stats(),
        'categories': categories,
    }

    return render(request, 'portal/pages/categories.html', context)


# Tariffs
@staff_member_required
def tariffs_list(request):
    """Tariffs list."""
    tariffs = Tariff.objects.annotate(users_count=Count('users'))

    context = {
        'active_page': 'tariffs',
        'stats': get_base_stats(),
        'tariffs': tariffs,
    }

    return render(request, 'portal/pages/tariffs.html', context)


# EPG
@staff_member_required
def epg_list(request):
    """EPG sources list."""
    from apps.epg.models import EpgSource

    sources = EpgSource.objects.all()

    context = {
        'active_page': 'epg',
        'stats': get_base_stats(),
        'sources': sources,
    }

    return render(request, 'portal/pages/epg.html', context)


# VOD
@staff_member_required
def vod_list(request):
    """VOD list."""
    from apps.vod.models import Movie, Series

    movies = Movie.objects.count()
    series = Series.objects.count()

    context = {
        'active_page': 'vod',
        'stats': get_base_stats(),
        'movies_count': movies,
        'series_count': series,
    }

    return render(request, 'portal/pages/vod.html', context)


# Streams
@staff_member_required
def streams_list(request):
    """Active streams list."""
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    active_devices = Device.objects.filter(
        last_seen__gte=online_threshold
    ).select_related('user', 'last_channel')

    context = {
        'active_page': 'streams',
        'stats': get_base_stats(),
        'active_devices': active_devices,
    }

    return render(request, 'portal/pages/streams.html', context)


# Logs
@staff_member_required
def logs_list(request):
    """Logs view."""
    context = {
        'active_page': 'logs',
        'stats': get_base_stats(),
    }

    return render(request, 'portal/pages/logs.html', context)


# Settings
@staff_member_required
def settings_view(request):
    """Settings view."""
    context = {
        'active_page': 'settings',
        'stats': get_base_stats(),
    }

    return render(request, 'portal/pages/settings.html', context)
