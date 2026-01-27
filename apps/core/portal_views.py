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

        # Handle password change
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            user.set_password(new_password)
            messages.success(request, 'Usuario y contrasena actualizados')
        else:
            messages.success(request, 'Usuario actualizado')

        user.save()
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
                name='Principal',
                priority=100,
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

        # Update stream URL (both in Channel and ChannelStream)
        stream_url = request.POST.get('stream_url')
        if stream_url:
            channel.stream_url = stream_url
        channel.save()

        if stream_url:
            # Get or create the primary stream (highest priority)
            stream = channel.streams.order_by('-priority').first()
            if stream:
                stream.url = stream_url
                stream.save()
            else:
                ChannelStream.objects.create(
                    channel=channel,
                    url=stream_url,
                    name='Principal',
                    priority=100,
                )

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
    """Import channels from M3U/M3U8."""
    if request.method == 'POST':
        m3u_file = request.FILES.get('m3u_file')
        m3u_text = request.POST.get('m3u_text', '').strip()

        if not m3u_file and not m3u_text:
            messages.error(request, 'Debes subir un archivo M3U o pegar el contenido')
            return redirect('portal:channels_import')

        # Get content
        if m3u_file:
            raw_content = m3u_file.read()
            try:
                content = raw_content.decode('utf-8')
            except UnicodeDecodeError:
                content = raw_content.decode('latin-1')
        else:
            content = m3u_text

        # Parse M3U
        channels_data = parse_m3u(content)

        if not channels_data:
            messages.error(request, 'No se encontraron canales válidos en el archivo')
            return redirect('portal:channels_import')

        # Import channels
        created = 0
        updated = 0
        errors = 0

        # Get max channel number
        max_number = Channel.objects.order_by('-number').values_list('number', flat=True).first() or 0

        for ch_data in channels_data:
            try:
                # Get or create category
                category = None
                if ch_data.get('group'):
                    category, _ = Category.objects.get_or_create(
                        name=ch_data['group'],
                        defaults={
                            'alias': slugify(ch_data['group']),
                            'is_active': True
                        }
                    )

                # Detect if radio
                is_radio = ch_data.get('group', '').lower() == 'radio'

                # Check if channel exists (by number, epg_id, or name)
                existing = None
                ch_number = ch_data.get('number')

                # First try by channel number (most reliable)
                if ch_number:
                    existing = Channel.objects.filter(number=ch_number).first()

                # Then try by epg_id
                if not existing and ch_data.get('tvg_id'):
                    existing = Channel.objects.filter(epg_id=ch_data['tvg_id']).first()

                # Finally try by name (exact match)
                if not existing:
                    existing = Channel.objects.filter(name__iexact=ch_data['name']).first()

                if existing:
                    # Update existing channel
                    existing.stream_url = ch_data['url']
                    if ch_data.get('logo'):
                        existing.logo_url = ch_data['logo']
                    if category:
                        existing.category = category
                    if ch_data.get('tvg_id'):
                        existing.epg_id = ch_data['tvg_id']
                    existing.is_hd = 'HD' in ch_data['name'].upper() or '1080' in ch_data['name']
                    existing.is_4k = '4K' in ch_data['name'].upper() or 'UHD' in ch_data['name'].upper()
                    existing.is_radio = is_radio
                    existing.save()

                    # Update or create stream
                    stream = existing.streams.order_by('-priority').first()
                    if stream:
                        stream.url = ch_data['url']
                        stream.save()
                    else:
                        ChannelStream.objects.create(
                            channel=existing,
                            url=ch_data['url'],
                            name='Principal',
                            priority=100,
                        )
                    updated += 1
                else:
                    # Create new channel - use provided number or next available
                    if ch_number:
                        new_number = ch_number
                    else:
                        max_number += 1
                        new_number = max_number

                    channel = Channel.objects.create(
                        name=ch_data['name'],
                        number=new_number,
                        stream_url=ch_data['url'],
                        logo_url=ch_data.get('logo', ''),
                        category=category,
                        epg_id=ch_data.get('tvg_id', ''),
                        is_hd='HD' in ch_data['name'].upper() or '1080' in ch_data['name'],
                        is_4k='4K' in ch_data['name'].upper() or 'UHD' in ch_data['name'].upper(),
                        is_radio=is_radio,
                        is_active=True
                    )
                    # Create stream
                    ChannelStream.objects.create(
                        channel=channel,
                        url=ch_data['url'],
                        name='Principal',
                        priority=100,
                    )
                    created += 1

            except Exception as e:
                errors += 1

        messages.success(request, f'Importación completada: {len(channels_data)} parseados, {created} creados, {updated} actualizados, {errors} errores')
        return redirect('portal:channels')

    # GET request - show import form
    context = {
        'active_page': 'channels',
        'stats': get_base_stats(),
    }
    return render(request, 'portal/pages/channels_import.html', context)


def parse_m3u(content):
    """Parse M3U/M3U8 content and extract channel data."""
    import re

    channels = []
    # Handle both Windows (\r\n) and Unix (\n) line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.strip().split('\n')

    current_channel = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('#EXTINF:'):
            # Parse EXTINF line
            current_channel = {}

            # Extract attributes
            # tvg-id
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            if tvg_id_match:
                current_channel['tvg_id'] = tvg_id_match.group(1)

            # tvg-chno (channel number)
            tvg_chno_match = re.search(r'tvg-chno="([^"]*)"', line)
            if tvg_chno_match:
                try:
                    current_channel['number'] = int(tvg_chno_match.group(1))
                except ValueError:
                    pass

            # tvg-name
            tvg_name_match = re.search(r'tvg-name="([^"]*)"', line)
            if tvg_name_match:
                current_channel['tvg_name'] = tvg_name_match.group(1)

            # tvg-logo
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_match:
                current_channel['logo'] = logo_match.group(1)

            # group-title
            group_match = re.search(r'group-title="([^"]*)"', line)
            if group_match:
                current_channel['group'] = group_match.group(1)

            # Channel name (after the last comma)
            name_match = re.search(r',\s*(.+)$', line)
            if name_match:
                current_channel['name'] = name_match.group(1).strip()
            elif tvg_name_match:
                current_channel['name'] = tvg_name_match.group(1)

        elif line and not line.startswith('#') and current_channel:
            # This is the URL line - clean Stalker "ffmpeg " prefix if present
            url = line
            if url.startswith('ffmpeg '):
                url = url[7:]  # Remove "ffmpeg " prefix
            current_channel['url'] = url
            if current_channel.get('name') and current_channel.get('url'):
                channels.append(current_channel)
            current_channel = None

    return channels


def slugify(text):
    """Simple slugify function."""
    import re
    text = text.lower()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text or 'sin-categoria'


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
    tariffs = Tariff.objects.prefetch_related('channels').annotate(users_count=Count('users'))
    categories = Category.objects.prefetch_related('channels').all()
    uncategorized_channels = Channel.objects.filter(category__isnull=True)

    context = {
        'active_page': 'tariffs',
        'stats': get_base_stats(),
        'tariffs': tariffs,
        'categories': categories,
        'uncategorized_channels': uncategorized_channels,
    }

    return render(request, 'portal/pages/tariffs.html', context)


@staff_member_required
def tariff_create(request):
    """Create new tariff."""
    if request.method == 'POST':
        tariff = Tariff.objects.create(
            name=request.POST.get('name'),
            price=request.POST.get('price', 0),
            duration_days=int(request.POST.get('duration_days', 0)),
            max_devices=int(request.POST.get('max_devices', 5)),
            max_concurrent_streams=int(request.POST.get('max_concurrent_streams', 2)),
            has_timeshift='has_timeshift' in request.POST,
            has_catchup='has_catchup' in request.POST,
            has_vod='has_vod' in request.POST,
            has_pvr='has_pvr' in request.POST,
        )

        # Añadir canales seleccionados
        channel_ids = request.POST.getlist('channels')
        if channel_ids:
            tariff.channels.set(channel_ids)

        messages.success(request, f'Tarifa {tariff.name} creada con {tariff.channels.count()} canales')

    return redirect('portal:tariffs')


@staff_member_required
def tariff_edit(request, tariff_id):
    """Edit tariff."""
    tariff = get_object_or_404(Tariff, id=tariff_id)

    if request.method == 'POST':
        tariff.name = request.POST.get('name')
        tariff.price = request.POST.get('price', 0)
        tariff.duration_days = int(request.POST.get('duration_days', 0))
        tariff.max_devices = int(request.POST.get('max_devices', 5))
        tariff.max_concurrent_streams = int(request.POST.get('max_concurrent_streams', 2))
        tariff.has_timeshift = 'has_timeshift' in request.POST
        tariff.has_catchup = 'has_catchup' in request.POST
        tariff.has_vod = 'has_vod' in request.POST
        tariff.has_pvr = 'has_pvr' in request.POST
        tariff.is_active = 'is_active' in request.POST
        tariff.save()

        # Actualizar canales
        channel_ids = request.POST.getlist('channels')
        tariff.channels.set(channel_ids)

        messages.success(request, 'Tarifa actualizada')
        return redirect('portal:tariffs')

    categories = Category.objects.prefetch_related('channels').all()
    uncategorized_channels = Channel.objects.filter(category__isnull=True)

    context = {
        'active_page': 'tariffs',
        'stats': get_base_stats(),
        'tariff': tariff,
        'categories': categories,
        'uncategorized_channels': uncategorized_channels,
    }

    return render(request, 'portal/pages/tariff_edit.html', context)


@staff_member_required
def tariff_delete(request, tariff_id):
    """Delete tariff."""
    if request.method == 'POST':
        tariff = get_object_or_404(Tariff, id=tariff_id)
        tariff.delete()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


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
