"""
Stalker Portal compatible API views.
"""
import hashlib
import time
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from apps.devices.models import Device
from apps.channels.models import Channel, Category
from apps.epg.models import Program
from apps.vod.models import Movie, Series, VodCategory
from .authentication import MACAuthentication


@never_cache
def stb_portal_app(request):
    """
    Serve the main STB portal application.
    This is loaded after successful authentication.
    """
    return render(request, 'stb/portal.html')


@never_cache
def stb_loader_page(request):
    """
    Serve initial loader page for MAG boxes.
    This page extracts the MAC or shows login form.
    """
    return render(request, 'stb/loader.html')


@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def portal_handler(request):
    """
    Main handler for Stalker portal requests.
    Routes to appropriate handler based on 'type' and 'action' params.
    """
    request_type = request.GET.get('type', request.POST.get('type', ''))
    action = request.GET.get('action', request.POST.get('action', ''))

    # Reset/logout endpoint
    if request.GET.get('logout') == '1':
        response = stb_loader_page(request)
        response.delete_cookie('mac')
        return response

    # If no params, serve appropriate page
    if not request_type and not action:
        mac = request.COOKIES.get('mac')
        if not mac:
            return stb_loader_page(request)

        # Verify MAC is valid (device exists)
        from .authentication import MACAuthentication
        normalized_mac = MACAuthentication.normalize_mac(mac)
        if normalized_mac:
            device_exists = Device.objects.filter(mac_address=normalized_mac, is_active=True).exists()
            if device_exists:
                return stb_portal_app(request)

        # Invalid MAC - clear cookie and show login
        response = stb_loader_page(request)
        response.delete_cookie('mac')
        return response

    # Route to appropriate handler
    handlers = {
        'stb': handle_stb,
        'itv': handle_itv,
        'vod': handle_vod,
        'series': handle_series,
        'epg': handle_epg,
        'tv_archive': handle_tv_archive,
        'pvr': handle_pvr,
        'records': handle_pvr,
        'watchdog': handle_watchdog,
        'account_info': handle_account_info,
    }

    handler = handlers.get(request_type, handle_unknown)
    return handler(request, action)


def stalker_response(data, js_callback=True):
    """Format response in Stalker portal format."""
    response_data = {
        'js': data
    }
    return JsonResponse(response_data)


# ============== Control parental ==============

PARENTAL_UNLOCK_SECONDS = 1800


def parental_unlocked(device):
    """
    True si este aparato ha metido el PIN hace poco.

    Si la cache no responde se responde que no: un control parental que se
    desactiva solo cuando se cae Redis no es un control parental. El precio es
    que mientras la cache este caida los canales de adultos no se ven.
    """
    if not device:
        return False
    try:
        return bool(cache.get(f'parental:{device.id}'))
    except Exception:
        return False


def parental_blocked(device, channel):
    """
    Un canal marcado como adulto pide PIN.

    Si el usuario no tiene PIN configurado no se bloquea nada: el control se
    activa poniendo la contrasena parental en su ficha.
    """
    if not channel.is_adult:
        return False
    if not device:
        return True
    if not device.user.parental_password:
        return False
    return not parental_unlocked(device)


def handle_check_pin(request):
    """Comprobar el PIN parental. El PIN nunca viaja al aparato."""
    from .throttle import too_many_attempts

    device = get_device_from_request(request)
    if not device:
        return stalker_response({'error': 'Not authenticated'})

    if too_many_attempts(request, scope='pin'):
        return stalker_response({'error': 'Demasiados intentos, espera unos minutos'})

    esperado = device.user.parental_password
    if not esperado:
        return stalker_response({'result': True, 'sin_pin': True})

    if request.GET.get('pin', '') != esperado:
        return stalker_response({'result': False, 'error': 'PIN incorrecto'})

    try:
        cache.set(f'parental:{device.id}', 1, PARENTAL_UNLOCK_SECONDS)
    except Exception:
        return stalker_response({'result': False, 'error': 'No se pudo desbloquear'})

    return stalker_response({'result': True})


def get_device_from_request(request):
    """Get authenticated device from request."""
    auth = MACAuthentication()
    try:
        result = auth.authenticate(request)
        if result:
            return result[1]  # Return device
    except Exception:
        pass
    return None


# ============== STB Handlers ==============

def handle_stb(request, action):
    """Handle STB (Set-Top Box) actions."""
    if action == 'handshake':
        return handle_handshake(request)
    elif action == 'get_profile':
        return handle_get_profile(request)
    elif action == 'do_auth':
        return handle_do_auth(request)
    elif action == 'login':
        return handle_login(request)
    elif action == 'get_localization':
        return handle_get_localization(request)
    elif action == 'get_modules':
        return handle_get_modules(request)
    elif action == 'check_pin':
        return handle_check_pin(request)
    elif action == 'log':
        return stalker_response({'result': True})

    return stalker_response({'error': 'Unknown action'})


def handle_login(request):
    """Handle login with username/password, return device MAC."""
    from django.contrib.auth import authenticate
    from .throttle import reset_attempts, too_many_attempts

    username = request.GET.get('login', request.POST.get('login', ''))
    password = request.GET.get('password', request.POST.get('password', ''))

    if not username:
        return stalker_response({'error': 'Usuario requerido'})

    if too_many_attempts(request):
        return stalker_response({'error': 'Demasiados intentos, espera unos minutos'})

    # Authenticate user
    user = authenticate(username=username, password=password)
    if not user:
        # Antes se aceptaba cualquier usuario existente sin comprobar la
        # contrasena, asi que conocer un nombre de usuario bastaba para entrar
        # y llevarse su MAC (que es la credencial de todo lo demas). Se sigue
        # permitiendo el acceso sin contrasena solo a las cuentas que
        # realmente no tienen ninguna puesta.
        from apps.accounts.models import User
        try:
            candidate = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return stalker_response({'error': 'Usuario no encontrado'})

        if candidate.has_usable_password():
            return stalker_response({'error': 'Contrasena incorrecta'})

        user = candidate

    # Get user's first active device, or create one
    device = user.devices.filter(is_active=True).first()
    if not device:
        # Generate a unique MAC for this device (AA = LG prefix)
        import random
        mac = 'AA:%02X:%02X:%02X:%02X:%02X' % (
            random.randint(0, 255), random.randint(0, 255),
            random.randint(0, 255), random.randint(0, 255),
            random.randint(0, 255)
        )
        device = Device.objects.create(
            user=user,
            mac_address=mac,
            is_active=True,
            name='LG TV - ' + user.username,
            device_type='lg',
        )

    reset_attempts(request)

    return stalker_response({
        'status': 1,
        'mac': device.mac_address,
        'user': user.username,
    })


def handle_handshake(request):
    """Initial handshake to get token."""
    device = get_device_from_request(request)

    if device:
        token = device.refresh_token()
    else:
        # Generate temporary token for unregistered device
        token = hashlib.md5(str(time.time()).encode()).hexdigest()

    return stalker_response({
        'token': token,
        'not_valid': 0 if device else 1,
    })


def handle_get_profile(request):
    """Get STB profile and settings."""
    device = get_device_from_request(request)

    if not device:
        return stalker_response({
            'id': 0,
            'name': '',
            'status': 0,
        })

    user = device.user

    return stalker_response({
        'id': device.id,
        'name': user.get_full_name() or user.username,
        'mac': device.mac_address,
        'status': 1 if user.is_subscription_active else 0,
        'tariff_plan_id': user.tariff_id or 0,
        'tariff_expired_date': user.subscription_expires.isoformat() if user.subscription_expires else '',
        'account_balance': str(user.balance),
        'fname': user.first_name,
        'lname': user.last_name,
        'phone': user.phone,
        'login': user.username,
        'ls': str(user.id),
        'max_online': user.max_concurrent_streams,
        'settings': {
            'volume': device.volume,
            'brightness': device.brightness,
            'language': device.language,
            'timezone': device.timezone,
        },
        'now': timezone.now().isoformat(),
    })


def handle_do_auth(request):
    """Authenticate device."""
    device = get_device_from_request(request)
    return stalker_response({
        'status': 1 if device else 0,
    })


def handle_get_localization(request):
    """Get localization strings."""
    return stalker_response({
        'result': {},
    })


def handle_get_modules(request):
    """Get available modules."""
    return stalker_response({
        'result': {
            'all_modules': ['tv', 'vod', 'epg', 'records', 'settings'],
            'disabled_modules': [],
        }
    })


# ============== ITV (Live TV) Handlers ==============

def handle_itv(request, action):
    """Handle ITV (Live TV) actions."""
    if action == 'get_all_channels':
        return handle_get_all_channels(request)
    elif action == 'get_ordered_list':
        return handle_get_ordered_list(request)
    elif action == 'get_genres':
        return handle_get_genres(request)
    elif action == 'get_url':
        return handle_get_url(request)
    elif action == 'get_short_epg':
        return handle_get_short_epg(request)
    elif action == 'set_fav':
        return handle_set_favorite(request)
    elif action == 'create_link':
        return handle_create_link(request)

    return stalker_response({'error': 'Unknown action'})


def handle_get_genres(request):
    """Get channel categories/genres."""
    categories = Category.objects.filter(is_active=True).order_by('order')

    data = []
    for cat in categories:
        data.append({
            'id': str(cat.id),
            'title': cat.name,
            'alias': cat.alias,
            'active_sub': True,
            'censored': cat.is_adult,
        })

    return stalker_response(data)


def handle_get_all_channels(request):
    """Get all channels."""
    return handle_get_ordered_list(request)


EMPTY_EPG = {
    'cur_playing': '',
    'epg_start': '',
    'epg_end': '',
    'epg_progress': 0,
    'epg_next': '',
    'epg_next_start': '',
    'epg_cur_start': '',
    'epg_cur_end': '',
}

EPG_CACHE_SECONDS = 60


def epg_now_next(channel_ids):
    """
    Ahora/despues de un grupo de canales, ya en el formato que espera el deco.

    Es identico para todos los usuarios, y get_ordered_list es lo que piden
    todos los aparatos al arrancar, asi que se cachea: era la parte mas cara de
    la respuesta. El progreso puede quedarse hasta un minuto desfasado, que en
    una barra no se nota.
    """
    if not channel_ids:
        return {}

    key = 'epg_nownext:' + hashlib.md5(
        ','.join(str(c) for c in sorted(channel_ids)).encode()
    ).hexdigest()
    try:
        cached = cache.get(key)
    except Exception:
        cached = None
    if cached is not None:
        return cached

    now = timezone.now()
    result = {}

    for p in Program.objects.filter(
        channel_id__in=channel_ids, start_time__lte=now, end_time__gte=now
    ):
        result[p.channel_id] = dict(
            EMPTY_EPG,
            cur_playing=p.title,
            epg_start=p.start_time.isoformat(),
            epg_end=p.end_time.isoformat(),
            epg_progress=p.progress_percent,
            epg_cur_start=timezone.localtime(p.start_time).strftime('%H:%M'),
            epg_cur_end=timezone.localtime(p.end_time).strftime('%H:%M'),
        )

    # Acotado a las proximas horas: sin el limite superior esta consulta traia
    # todos los programas futuros (dias) de 50 canales para quedarse con uno
    # por canal.
    seen = set()
    for p in Program.objects.filter(
        channel_id__in=channel_ids,
        start_time__gt=now,
        start_time__lte=now + timezone.timedelta(hours=6),
    ).order_by('channel_id', 'start_time'):
        if p.channel_id in seen:
            continue
        seen.add(p.channel_id)
        entry = result.setdefault(p.channel_id, dict(EMPTY_EPG))
        entry['epg_next'] = p.title
        entry['epg_next_start'] = timezone.localtime(p.start_time).strftime('%H:%M')

    try:
        cache.set(key, result, EPG_CACHE_SECONDS)
    except Exception:
        pass

    return result


def handle_get_ordered_list(request):
    """Get ordered channel list."""
    device = get_device_from_request(request)
    genre_id = request.GET.get('genre', '*')
    page = int(request.GET.get('p', 0))
    per_page = 50

    channels = Channel.objects.filter(is_active=True).order_by('number')

    if genre_id and genre_id != '*':
        channels = channels.filter(category_id=genre_id)

    # Filter by user's packages if authenticated
    if device and device.user.tariff:
        package_ids = device.user.tariff.channel_packages.values_list('id', flat=True)
        from django.db.models import Q
        channels = channels.filter(
            Q(packages__id__in=package_ids) | Q(packages__isnull=True)
        ).distinct()

    total = channels.count()
    channels = channels[page * per_page:(page + 1) * per_page]

    epg = epg_now_next([ch.id for ch in channels])

    favorites = set()
    if device:
        from apps.channels.models import Favorite
        favorites = set(
            Favorite.objects.filter(user=device.user).values_list('channel_id', flat=True)
        )

    # Se resuelve una vez y no por canal: mirar la cache 50 veces por peticion
    # no tiene sentido.
    tiene_pin = bool(device and device.user.parental_password)
    desbloqueado = parental_unlocked(device) if tiene_pin else True

    data = []
    for ch in channels:
        # Only advertise archive when a recorder can actually serve it: it needs
        # catchup enabled and a multicast source being archived.
        has_archive = bool(ch.has_catchup and ch.multicast_url)
        # Un canal de adultos bloqueado no viaja con su URL: si se mandara,
        # pedir el PIN en pantalla seria un adorno que cualquiera se salta.
        bloqueado = bool(ch.is_adult and tiene_pin and not desbloqueado)
        entry = {
            'id': str(ch.id),
            'name': ch.name,
            'number': ch.number,
            'cmd': '' if bloqueado else ch.stream_url,
            'locked': 1 if bloqueado else 0,
            'logo': ch.logo_display_url,
            'censored': ch.is_adult,
            'hd': 1 if ch.is_hd else 0,
            'fav': 1 if ch.id in favorites else 0,
            'archive': 1 if has_archive else 0,
            'archive_range': ch.timeshift_hours if has_archive else 0,
            'genre_id': str(ch.category_id) if ch.category_id else '',
        }
        entry.update(epg.get(ch.id, EMPTY_EPG))
        data.append(entry)

    return stalker_response({
        'total_items': total,
        'max_page_items': per_page,
        'data': data,
    })


def handle_get_url(request):
    """Get stream URL for a channel."""
    cmd = request.GET.get('cmd', '')
    device = get_device_from_request(request)

    # cmd could be channel ID or direct URL
    if cmd.isdigit():
        try:
            channel = Channel.objects.get(id=cmd, is_active=True)
        except Channel.DoesNotExist:
            return stalker_response({'error': 'Channel not found'})

        if parental_blocked(device, channel):
            return stalker_response({'error': 'Canal bloqueado, introduce el PIN'})

        stream_url = channel.stream_url
    else:
        stream_url = cmd

    # Add authentication token if needed
    if device:
        separator = '&' if '?' in stream_url else '?'
        stream_url = f"{stream_url}{separator}token={device.token}"

    return stalker_response({
        'cmd': stream_url,
    })


def handle_create_link(request):
    """Create streaming link (alias for get_url)."""
    return handle_get_url(request)


def handle_get_short_epg(request):
    """Get short EPG for channel."""
    channel_id = request.GET.get('ch_id')
    if not channel_id:
        return stalker_response({'data': []})

    now = timezone.now()
    programs = Program.objects.filter(
        channel_id=channel_id,
        end_time__gte=now
    ).order_by('start_time')[:10]

    data = []
    for prog in programs:
        data.append({
            'id': str(prog.id),
            't_time': timezone.localtime(prog.start_time).strftime('%H:%M'),
            't_time_end': timezone.localtime(prog.end_time).strftime('%H:%M'),
            'name': prog.title,
            'descr': prog.description[:200] if prog.description else '',
            'start_timestamp': int(prog.start_time.timestamp()),
            'stop_timestamp': int(prog.end_time.timestamp()),
            'progress': prog.progress_percent,
        })

    return stalker_response({'data': data})


def handle_set_favorite(request):
    """Set channel as favorite."""
    device = get_device_from_request(request)
    if not device:
        return stalker_response({'error': 'Not authenticated'})

    ch_id = request.GET.get('ch_id')
    fav = request.GET.get('fav', '1')

    from apps.channels.models import Favorite

    if fav == '1':
        Favorite.objects.get_or_create(
            user=device.user,
            channel_id=ch_id
        )
    else:
        Favorite.objects.filter(
            user=device.user,
            channel_id=ch_id
        ).delete()

    return stalker_response({'result': True})


# ============== VOD Handlers ==============

def handle_vod(request, action):
    """Handle VOD actions."""
    if action == 'get_categories':
        return handle_vod_categories(request)
    elif action == 'get_ordered_list':
        return handle_vod_list(request)
    elif action == 'create_link':
        return handle_vod_link(request)

    return stalker_response({'error': 'Unknown action'})


def vod_disponible(request):
    """
    Comprueba que el aparato puede ver VOD.

    Devuelve (device, respuesta_de_error). La tarifa manda: hasta ahora el
    catalogo se servia sin mirar si estaba incluido.
    """
    device = get_device_from_request(request)
    if not device:
        return None, stalker_response({'error': 'Not authenticated'})
    if device.user.tariff and not device.user.tariff.has_vod:
        return None, stalker_response({'error': 'Videoclub no incluido en tu tarifa'})
    return device, None


def vod_adulto_bloqueado(device, obj):
    """Las peliculas y series +18 piden el mismo PIN que los canales."""
    if not getattr(obj, 'is_adult', False):
        return False
    if not device:
        return True
    if not device.user.parental_password:
        return False
    return not parental_unlocked(device)


def handle_vod_categories(request):
    """Get VOD categories."""
    categories = VodCategory.objects.filter(is_active=True).order_by('order')

    data = []
    for cat in categories:
        data.append({
            'id': str(cat.id),
            'title': cat.name,
            'alias': cat.alias,
            'censored': cat.is_adult,
        })

    return stalker_response(data)


def handle_vod_list(request):
    """Get VOD list."""
    device, error = vod_disponible(request)
    if error:
        return error

    category_id = request.GET.get('category')
    page = int(request.GET.get('p', 0))
    per_page = 50

    movies = Movie.objects.filter(is_active=True)

    if category_id and category_id != '*':
        movies = movies.filter(category_id=category_id)

    busqueda = request.GET.get('search', '').strip()
    if busqueda:
        movies = movies.filter(title__icontains=busqueda)

    total = movies.count()
    movies = movies[page * per_page:(page + 1) * per_page]

    data = []
    for movie in movies:
        bloqueada = vod_adulto_bloqueado(device, movie)
        data.append({
            'locked': 1 if bloqueada else 0,
            'id': str(movie.id),
            'name': movie.title,
            'o_name': movie.original_title,
            'description': movie.description[:500] if movie.description else '',
            'director': movie.director,
            'actors': movie.cast,
            'year': str(movie.year) if movie.year else '',
            'rating_imdb': str(movie.rating) if movie.rating else '',
            'time': str(movie.duration) if movie.duration else '',
            'screenshot_uri': movie.poster_url or '',
            'hd': 1 if movie.is_hd else 0,
            'genres': movie.genres,
            # Como en los canales: si esta bloqueada no viaja la URL.
            'cmd': '' if bloqueada else movie.stream_url,
        })

    return stalker_response({
        'total_items': total,
        'max_page_items': per_page,
        'data': data,
    })


def handle_vod_link(request):
    """Get VOD stream link."""
    cmd = request.GET.get('cmd', '')
    device, error = vod_disponible(request)
    if error:
        return error

    if cmd.isdigit():
        try:
            movie = Movie.objects.get(id=cmd, is_active=True)
        except Movie.DoesNotExist:
            return stalker_response({'error': 'Movie not found'})

        if vod_adulto_bloqueado(device, movie):
            return stalker_response({'error': 'Contenido bloqueado, introduce el PIN'})

        stream_url = movie.stream_url
    else:
        stream_url = cmd

    if device:
        separator = '&' if '?' in stream_url else '?'
        stream_url = f"{stream_url}{separator}token={device.token}"

    return stalker_response({'cmd': stream_url})


# ============== Series Handlers ==============

def handle_series(request, action):
    """Handle Series actions."""
    if action == 'get_categories':
        return handle_vod_categories(request)
    elif action == 'get_ordered_list':
        return handle_series_list(request)
    elif action in ('get_episodes', 'get_seasons'):
        return handle_series_episodes(request)
    elif action == 'create_link':
        return handle_series_link(request)

    return stalker_response({'error': 'Unknown action'})


def handle_series_episodes(request):
    """
    Capitulos de una serie, en una sola lista ordenada por temporada.

    Sin esto se podia listar el catalogo de series pero no llegar a ver nada:
    no habia forma de pedir los capitulos.
    """
    from apps.vod.models import Episode

    device, error = vod_disponible(request)
    if error:
        return error

    series_id = request.GET.get('series_id') or request.GET.get('cmd')
    try:
        serie = Series.objects.get(id=series_id, is_active=True)
    except (Series.DoesNotExist, ValueError, TypeError):
        return stalker_response({'error': 'Serie no encontrada'})

    bloqueada = vod_adulto_bloqueado(device, serie)

    episodios = Episode.objects.filter(
        season__series=serie, is_active=True
    ).select_related('season').order_by('season__number', 'number')

    data = []
    for ep in episodios:
        data.append({
            'id': str(ep.id),
            'season': ep.season.number,
            'episode': ep.number,
            'name': ep.title,
            'label': f'T{ep.season.number}E{ep.number:02d} {ep.title}',
            'description': ep.description[:500] if ep.description else '',
            'time': str(ep.duration) if ep.duration else '',
            'screenshot_uri': ep.poster_url or '',
            'locked': 1 if bloqueada else 0,
            'cmd': '' if bloqueada else str(ep.id),
        })

    return stalker_response({
        'series': serie.title,
        'total_items': len(data),
        'data': data,
    })


def handle_series_link(request):
    """URL de reproduccion de un capitulo."""
    from apps.vod.models import Episode

    device, error = vod_disponible(request)
    if error:
        return error

    cmd = request.GET.get('cmd', '')
    try:
        episodio = Episode.objects.select_related('season__series').get(
            id=cmd, is_active=True
        )
    except (Episode.DoesNotExist, ValueError):
        return stalker_response({'error': 'Capitulo no encontrado'})

    if vod_adulto_bloqueado(device, episodio.season.series):
        return stalker_response({'error': 'Contenido bloqueado, introduce el PIN'})

    stream_url = episodio.stream_url
    if device:
        separator = '&' if '?' in stream_url else '?'
        stream_url = f"{stream_url}{separator}token={device.token}"

    return stalker_response({'cmd': stream_url})


def handle_series_list(request):
    """Get series list."""
    device, error = vod_disponible(request)
    if error:
        return error

    category_id = request.GET.get('category')
    page = int(request.GET.get('p', 0))
    per_page = 50

    series = Series.objects.filter(is_active=True)

    if category_id and category_id != '*':
        series = series.filter(category_id=category_id)

    busqueda = request.GET.get('search', '').strip()
    if busqueda:
        series = series.filter(title__icontains=busqueda)

    total = series.count()
    series_list = series[page * per_page:(page + 1) * per_page]

    data = []
    for s in series_list:
        data.append({
            'locked': 1 if vod_adulto_bloqueado(device, s) else 0,
            'id': str(s.id),
            'name': s.title,
            'o_name': s.original_title,
            'description': s.description[:500] if s.description else '',
            'actors': s.cast,
            'year': str(s.year_start) if s.year_start else '',
            'rating_imdb': str(s.rating) if s.rating else '',
            'screenshot_uri': s.poster_url or '',
            'series': s.seasons.count(),
        })

    return stalker_response({
        'total_items': total,
        'max_page_items': per_page,
        'data': data,
    })


# ============== EPG Handlers ==============

def handle_epg(request, action):
    """Handle EPG actions."""
    if action == 'get_simple_data_table':
        return handle_epg_table(request)
    elif action == 'get_week':
        return handle_epg_week(request)

    return stalker_response({'error': 'Unknown action'})


def handle_epg_table(request):
    """Get EPG data table."""
    channel_id = request.GET.get('ch_id')
    date = request.GET.get('date')

    if not channel_id:
        return stalker_response({'data': []})

    from datetime import datetime, timedelta

    if date:
        try:
            day = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            day = timezone.now().date()
    else:
        day = timezone.now().date()

    programs = Program.objects.filter(
        channel_id=channel_id,
        start_time__date=day
    ).order_by('start_time')

    device = get_device_from_request(request)
    scheduled = set()
    if device:
        from apps.pvr.models import Recording
        scheduled = set(
            Recording.objects.filter(
                user=device.user, program__in=programs
            ).values_list('program_id', flat=True)
        )

    now = timezone.now()
    data = []
    for prog in programs:
        data.append({
            'id': str(prog.id),
            't_time': timezone.localtime(prog.start_time).strftime('%H:%M'),
            't_time_end': timezone.localtime(prog.end_time).strftime('%H:%M'),
            'name': prog.title,
            'descr': prog.description or '',
            'category': prog.category or '',
            # Extras used by our portal (MAG ignores unknown keys)
            'start_timestamp': int(prog.start_time.timestamp()),
            'stop_timestamp': int(prog.end_time.timestamp()),
            'progress': prog.progress_percent,
            'past': 1 if prog.end_time < now else 0,
            'current': 1 if prog.start_time <= now <= prog.end_time else 0,
            'rec': 1 if prog.id in scheduled else 0,
        })

    return stalker_response({'data': data})


def handle_epg_week(request):
    """Get EPG for a week."""
    channel_id = request.GET.get('ch_id')
    if not channel_id:
        return stalker_response({'data': []})

    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)
    week_ahead = now + timezone.timedelta(days=7)

    programs = Program.objects.filter(
        channel_id=channel_id,
        start_time__gte=week_ago,
        start_time__lte=week_ahead
    ).order_by('start_time')

    data = {}
    for prog in programs:
        day_key = timezone.localtime(prog.start_time).strftime('%Y-%m-%d')
        if day_key not in data:
            data[day_key] = []

        data[day_key].append({
            'id': str(prog.id),
            't_time': timezone.localtime(prog.start_time).strftime('%H:%M'),
            't_time_end': timezone.localtime(prog.end_time).strftime('%H:%M'),
            'name': prog.title,
            'descr': prog.description[:200] if prog.description else '',
        })

    return stalker_response({'data': data})


# ============== TV Archive / Timeshift Handlers ==============

def handle_tv_archive(request, action):
    """Handle TV archive/timeshift actions."""
    if action == 'create_link':
        return handle_archive_link(request)

    return stalker_response({'error': 'Unknown action'})


def handle_archive_link(request):
    """
    Create a timeshift/archive link.

    The archive lives on the storage server as hourly MPEG-TS pieces, served by
    its get.php. Pointing at the CDN's live HLS with an ?utc= parameter never
    worked: that server has no archive, it only holds seconds of stream in RAM.
    """
    from datetime import datetime, timezone as dt_timezone
    from .storage_views import build_catchup_url

    device = get_device_from_request(request)

    channel_id = request.GET.get('ch_id')
    utc = request.GET.get('utc')
    lutc = request.GET.get('lutc')

    if not channel_id:
        return stalker_response({'error': 'Channel ID required'})

    try:
        channel = Channel.objects.get(id=channel_id, is_active=True)
    except Channel.DoesNotExist:
        return stalker_response({'error': 'Channel not found'})

    if parental_blocked(device, channel):
        return stalker_response({'error': 'Canal bloqueado, introduce el PIN'})

    if not channel.has_catchup or not channel.multicast_url:
        return stalker_response({'error': 'Archivo no disponible para este canal'})

    if device and device.user.tariff and not device.user.tariff.has_catchup:
        return stalker_response({'error': 'Archivo no incluido en tu tarifa'})

    if not utc:
        return stalker_response({'error': 'utc required'})

    try:
        start = datetime.fromtimestamp(int(utc), tz=dt_timezone.utc)
    except (TypeError, ValueError):
        return stalker_response({'error': 'utc invalid'})

    # Do not serve beyond what the recorder keeps.
    oldest = timezone.now() - timezone.timedelta(hours=channel.timeshift_hours)
    if start < oldest:
        return stalker_response({'error': 'El programa ya no está en el archivo'})

    duration = 3600
    if lutc:
        try:
            duration = max(60, int(lutc) - int(utc))
        except (TypeError, ValueError):
            pass

    url = build_catchup_url(channel, start, duration, device)
    if not url:
        return stalker_response({'error': 'No hay servidor de archivo configurado'})

    return stalker_response({'cmd': url})


# ============== PVR (Recordings) Handlers ==============

def handle_pvr(request, action):
    """Handle recording actions coming from MAG boxes."""
    if action in ('get_ordered_list', 'get_recordings', 'get_list'):
        return handle_pvr_list(request)
    elif action in ('create_task', 'add_task', 'record'):
        return handle_pvr_create(request)
    elif action in ('delete_task', 'stop_task', 'remove'):
        return handle_pvr_delete(request)
    elif action == 'create_link':
        return handle_pvr_link(request)

    return stalker_response({'error': 'Unknown action'})


def _pvr_device(request):
    device = get_device_from_request(request)
    if not device:
        return None, stalker_response({'error': 'Not authenticated'})
    if device.user.tariff and not device.user.tariff.has_pvr:
        return None, stalker_response({'error': 'Grabaciones no incluidas en tu tarifa'})
    return device, None


def handle_pvr_list(request):
    """List the user's recordings."""
    from apps.pvr.models import Recording

    device, error = _pvr_device(request)
    if error:
        return error

    recordings = Recording.objects.filter(
        user=device.user
    ).select_related('channel').order_by('-start_time')

    data = []
    for rec in recordings:
        data.append({
            'id': str(rec.id),
            'name': rec.title,
            'ch_id': str(rec.channel_id),
            'ch_name': rec.channel.name,
            'start_time': timezone.localtime(rec.start_time).strftime('%Y-%m-%d %H:%M'),
            'end_time': timezone.localtime(rec.end_time).strftime('%Y-%m-%d %H:%M'),
            'status': rec.status,
            'ready': 1 if rec.status == 'completed' else 0,
            'length': rec.duration or 0,
            'cmd': str(rec.id),
        })

    return stalker_response({
        'total_items': len(data),
        'max_page_items': len(data),
        'data': data,
    })


def handle_pvr_create(request):
    """Schedule a recording, either from an EPG program or a raw time range."""
    from datetime import datetime, timezone as dt_timezone
    from apps.pvr.models import Recording

    device, error = _pvr_device(request)
    if error:
        return error

    program_id = request.GET.get('program_id') or request.GET.get('epg_id')
    channel_id = request.GET.get('ch_id')

    if program_id:
        try:
            program = Program.objects.select_related('channel').get(id=program_id)
        except Program.DoesNotExist:
            return stalker_response({'error': 'Programa no encontrado'})

        if Recording.objects.filter(user=device.user, program=program).exists():
            return stalker_response({'error': 'Ya está programada'})

        recording = Recording.objects.create(
            user=device.user,
            channel=program.channel,
            program=program,
            title=program.title,
            description=program.description,
            start_time=program.start_time,
            end_time=program.end_time,
        )
        return stalker_response({'id': recording.id, 'result': True})

    if not channel_id:
        return stalker_response({'error': 'ch_id o program_id requerido'})

    try:
        channel = Channel.objects.get(id=channel_id, is_active=True)
    except Channel.DoesNotExist:
        return stalker_response({'error': 'Canal no encontrado'})

    try:
        start = datetime.fromtimestamp(int(request.GET.get('start', 0)), tz=dt_timezone.utc)
        end = datetime.fromtimestamp(int(request.GET.get('end', 0)), tz=dt_timezone.utc)
    except (TypeError, ValueError):
        return stalker_response({'error': 'start/end inválidos'})

    if end <= start:
        return stalker_response({'error': 'Rango de tiempo inválido'})

    recording = Recording.objects.create(
        user=device.user,
        channel=channel,
        title=request.GET.get('name', channel.name),
        start_time=start,
        end_time=end,
    )
    return stalker_response({'id': recording.id, 'result': True})


def handle_pvr_delete(request):
    """Cancel a scheduled recording or delete a finished one."""
    from apps.pvr.models import Recording, RecordingStatus
    from apps.pvr import storage_client

    device, error = _pvr_device(request)
    if error:
        return error

    rec_id = request.GET.get('id') or request.GET.get('cmd')
    try:
        recording = Recording.objects.get(id=rec_id, user=device.user)
    except (Recording.DoesNotExist, ValueError):
        return stalker_response({'error': 'Grabación no encontrada'})

    if recording.status == RecordingStatus.RECORDING and recording.storage:
        try:
            storage_client.stop_recording(recording.storage, recording.id)
        except storage_client.StorageError:
            pass

    if recording.storage and recording.filename:
        try:
            storage_client.delete_recording_file(recording.storage, recording.filename)
        except storage_client.StorageError:
            pass

    recording.delete()
    return stalker_response({'result': True})


def handle_pvr_link(request):
    """Return the playback URL of a finished recording."""
    from apps.pvr.models import Recording, RecordingStatus

    device, error = _pvr_device(request)
    if error:
        return error

    rec_id = request.GET.get('cmd') or request.GET.get('id')
    try:
        recording = Recording.objects.get(id=rec_id, user=device.user)
    except (Recording.DoesNotExist, ValueError):
        return stalker_response({'error': 'Grabación no encontrada'})

    if recording.status != RecordingStatus.COMPLETED:
        return stalker_response({'error': 'La grabación aún no está lista'})

    url = recording.stream_url
    if not url and recording.storage and recording.filename:
        url = recording.storage.build_url(recording.filename, public=True)

    if not url:
        return stalker_response({'error': 'Grabación sin fichero'})

    return stalker_response({'cmd': url})


# ============== Other Handlers ==============

def handle_watchdog(request, action):
    """
    Handle watchdog/keepalive.

    La actividad ya se anota (agrupada) al autenticar, que es por donde pasan
    todas las peticiones del aparato. Aqui solo se guarda el canal que esta
    viendo, que es lo que hace falta para la pantalla de streams activos: sin
    esto un aparato que lleva media hora con un canal puesto no vuelve a pedir
    nada y parece apagado.
    """
    device = get_device_from_request(request)

    if device:
        ch_id = request.GET.get('ch_id', '')
        if ch_id.isdigit() and str(device.last_channel_id or '') != ch_id:
            canal = Channel.objects.filter(id=ch_id, is_active=True).first()
            if canal:
                device.update_activity(channel=canal)

    return stalker_response({'result': True})


def handle_account_info(request, action):
    """Handle account info requests."""
    device = get_device_from_request(request)
    if not device:
        return stalker_response({'error': 'Not authenticated'})

    user = device.user
    return stalker_response({
        'id': user.id,
        'login': user.username,
        'fname': user.first_name,
        'lname': user.last_name,
        'tariff_plan': user.tariff.name if user.tariff else '',
        'tariff_expired_date': user.subscription_expires.isoformat() if user.subscription_expires else '',
        'account_balance': str(user.balance),
    })


def handle_unknown(request, action):
    """Handle unknown request types."""
    return stalker_response({
        'error': f'Unknown type/action: {request.GET.get("type")}/{action}'
    })
