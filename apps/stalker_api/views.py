"""
Stalker Portal compatible API views.
"""
import hashlib
import time
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from apps.devices.models import Device
from apps.channels.models import Channel, Category
from apps.epg.models import Program
from apps.vod.models import Movie, Series, VodCategory
from .authentication import MACAuthentication


def stb_portal_app(request):
    """
    Serve the main STB portal application.
    This is loaded after successful authentication.
    """
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>QuattreTV</title>
    <script>
    var stbAPI = null;
    var currentMenu = 0;
    var currentChannel = 0;
    var channels = [];
    var categories = [];
    var currentCategory = 0;
    var isPlaying = false;
    var osdVisible = true;
    var osdTimer = null;
    var viewMode = 'menu'; // menu, channels, fullscreen

    function initSTB() {
        // Detect STB API
        if (typeof(gSTB) !== 'undefined') {
            stbAPI = gSTB;
        } else if (typeof(stb) !== 'undefined') {
            stbAPI = stb;
        }

        if (stbAPI) {
            try {
                stbAPI.InitPlayer();
                stbAPI.SetViewport(0, 0, 1920, 1080);
                stbAPI.SetWinMode(1, 1); // Fullscreen video
                stbAPI.SetTopWin(1); // Browser on top
                stbAPI.SetTransparentColor(0x000001);
                stbAPI.SetChromaKey(0x000001, 0xffffff);
            } catch(e) { console.log('STB init error:', e); }
        }

        loadCategories();
    }

    function loadCategories() {
        ajax('?type=itv&action=get_genres', function(data) {
            if (data.js) {
                categories = [{id: '*', title: 'Todos'}].concat(data.js);
                loadChannels();
            }
        });
    }

    function loadChannels() {
        var catId = categories[currentCategory] ? categories[currentCategory].id : '*';
        ajax('?type=itv&action=get_ordered_list&genre=' + catId + '&p=0', function(data) {
            if (data.js && data.js.data) {
                channels = data.js.data;
                currentChannel = 0;
                render();
            }
        });
    }

    function ajax(url, callback) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState == 4 && xhr.status == 200) {
                try { callback(JSON.parse(xhr.responseText)); } catch(e) {}
            }
        };
        xhr.send();
    }

    function render() {
        if (viewMode == 'fullscreen') {
            renderOSD();
            return;
        }

        var html = '';

        // Header
        html += '<div class="header"><div class="logo">QuattreTV</div></div>';

        // Categories bar
        html += '<div class="categories">';
        for (var i = 0; i < categories.length && i < 10; i++) {
            html += '<span class="cat' + (i == currentCategory ? ' active' : '') + '">' + categories[i].title + '</span>';
        }
        html += '</div>';

        // Channel list
        html += '<div class="channels">';
        var start = Math.max(0, currentChannel - 4);
        var end = Math.min(channels.length, start + 9);
        for (var i = start; i < end; i++) {
            var ch = channels[i];
            html += '<div class="channel' + (i == currentChannel ? ' active' : '') + '">';
            if (ch.logo) html += '<img class="logo" src="' + ch.logo + '" onerror="this.style.display=\'none\'">';
            html += '<div class="info"><div class="name">' + ch.number + '. ' + ch.name + '</div>';
            if (ch.cur_playing) html += '<div class="epg">' + ch.cur_playing + '</div>';
            html += '</div></div>';
        }
        html += '</div>';

        // Footer
        html += '<div class="footer">';
        html += '<span class="key">OK</span> Ver &nbsp; ';
        html += '<span class="key">&#9650;&#9660;</span> Navegar &nbsp; ';
        html += '<span class="key">&#9664;&#9654;</span> Categoria';
        html += '</div>';

        document.getElementById('osd').innerHTML = html;
        document.getElementById('osd').style.display = 'block';
    }

    function renderOSD() {
        if (!osdVisible) {
            document.getElementById('osd').style.display = 'none';
            return;
        }
        var ch = channels[currentChannel];
        if (!ch) return;

        var html = '<div class="osd-bar">';
        html += '<div class="osd-channel">' + ch.number + '. ' + ch.name + '</div>';
        if (ch.cur_playing) html += '<div class="osd-epg">' + ch.cur_playing + '</div>';
        html += '<div class="osd-hint">OK: Lista &nbsp; CH+/-: Cambiar</div>';
        html += '</div>';

        document.getElementById('osd').innerHTML = html;
        document.getElementById('osd').style.display = 'block';
    }

    function showOSD() {
        osdVisible = true;
        renderOSD();
        clearTimeout(osdTimer);
        osdTimer = setTimeout(function() {
            osdVisible = false;
            document.getElementById('osd').style.display = 'none';
        }, 5000);
    }

    function playChannel(index) {
        if (index < 0 || index >= channels.length) return;
        currentChannel = index;
        var ch = channels[currentChannel];

        ajax('?type=itv&action=get_url&cmd=' + encodeURIComponent(ch.cmd || ch.id), function(data) {
            if (data.js && data.js.cmd) {
                var url = data.js.cmd;
                if (stbAPI) {
                    try {
                        stbAPI.Play(url);
                        isPlaying = true;
                        viewMode = 'fullscreen';
                        document.body.style.background = 'transparent';
                        document.getElementById('osd').className = 'playing';
                        showOSD();
                    } catch(e) { console.log('Play error:', e); }
                } else {
                    document.getElementById('osd').innerHTML = '<div class="no-stb">URL: ' + url + '</div>';
                }
            }
        });
    }

    function stopPlayback() {
        if (stbAPI && isPlaying) {
            try { stbAPI.Stop(); } catch(e) {}
            isPlaying = false;
        }
        viewMode = 'menu';
        document.body.style.background = '#0a0f1e';
        document.getElementById('osd').className = '';
        render();
    }

    document.onkeydown = function(e) {
        var key = e.keyCode;

        if (viewMode == 'fullscreen') {
            // Fullscreen mode controls
            if (key == 38 || key == 33) { // Up or CH+
                playChannel(currentChannel - 1);
            } else if (key == 40 || key == 34) { // Down or CH-
                playChannel(currentChannel + 1);
            } else if (key == 13) { // OK - show channel list
                stopPlayback();
            } else if (key == 8 || key == 27 || key == 461) { // Back
                stopPlayback();
            } else if (key == 73) { // Info
                showOSD();
            } else {
                showOSD();
            }
        } else {
            // Menu mode controls
            if (key == 37) { // Left - prev category
                if (currentCategory > 0) {
                    currentCategory--;
                    loadChannels();
                }
            } else if (key == 39) { // Right - next category
                if (currentCategory < categories.length - 1) {
                    currentCategory++;
                    loadChannels();
                }
            } else if (key == 38) { // Up
                if (currentChannel > 0) currentChannel--;
                render();
            } else if (key == 40) { // Down
                if (currentChannel < channels.length - 1) currentChannel++;
                render();
            } else if (key == 13) { // OK - play
                playChannel(currentChannel);
            } else if (key == 33) { // Page Up
                currentChannel = Math.max(0, currentChannel - 9);
                render();
            } else if (key == 34) { // Page Down
                currentChannel = Math.min(channels.length - 1, currentChannel + 9);
                render();
            }
        }

        e.preventDefault();
        return false;
    };

    window.onload = initSTB;
    </script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0f1e; color: #fff; font-family: Arial, sans-serif; overflow: hidden; }

        #osd { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: #0a0f1e; }
        #osd.playing { background: transparent; }

        .header { padding: 20px 40px; background: linear-gradient(90deg, #e94560 0%, #1a1a2e 100%); }
        .header .logo { font-size: 28px; font-weight: bold; }

        .categories { padding: 15px 40px; background: #16213e; display: flex; gap: 5px; overflow: hidden; }
        .cat { padding: 8px 20px; border-radius: 20px; font-size: 14px; white-space: nowrap; }
        .cat.active { background: #e94560; }

        .channels { padding: 20px 40px; height: calc(100vh - 180px); overflow: hidden; }
        .channel { display: flex; align-items: center; padding: 15px 20px; margin: 5px 0; border-radius: 8px; background: rgba(255,255,255,0.05); }
        .channel.active { background: #e94560; transform: scale(1.02); }
        .channel .logo { width: 60px; height: 40px; object-fit: contain; margin-right: 15px; }
        .channel .info { flex: 1; }
        .channel .name { font-size: 20px; font-weight: 500; }
        .channel .epg { font-size: 14px; color: #aaa; margin-top: 3px; }
        .channel.active .epg { color: #ffd; }

        .footer { position: fixed; bottom: 0; left: 0; right: 0; padding: 15px 40px; background: #16213e; font-size: 14px; color: #888; }
        .key { background: #333; padding: 3px 8px; border-radius: 3px; color: #fff; }

        .osd-bar { position: fixed; bottom: 50px; left: 50px; right: 50px; padding: 20px 30px; background: rgba(0,0,0,0.85); border-radius: 10px; border-left: 4px solid #e94560; }
        .osd-channel { font-size: 24px; font-weight: bold; }
        .osd-epg { font-size: 16px; color: #aaa; margin-top: 5px; }
        .osd-hint { font-size: 12px; color: #666; margin-top: 10px; }

        .no-stb { padding: 50px; text-align: center; background: #1a1a2e; }
    </style>
</head>
<body>
    <div id="osd">Cargando...</div>
</body>
</html>'''
    return HttpResponse(html, content_type='text/html')


def stb_loader_page(request):
    """
    Serve initial loader page for MAG boxes.
    This page extracts the MAC or shows login form.
    """
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>QuattreTV</title>
    <script>
    function log(msg) {
        document.getElementById('msg').innerHTML = msg;
    }

    function setMacAndReload(mac) {
        mac = mac.replace(/%3A/g, ':').replace(/-/g, ':').toUpperCase().trim();
        document.cookie = 'mac=' + mac + '; path=/; max-age=31536000';
        setTimeout(function() { location.reload(); }, 200);
    }

    function initApp() {
        var mac = '';
        try {
            if (typeof(Android) !== 'undefined') {
                if (Android.getMac) mac = Android.getMac();
                else if (Android.getMAC) mac = Android.getMAC();
            }
            if (!mac && typeof(stb) !== 'undefined' && stb.GetDeviceMAC) {
                mac = stb.GetDeviceMAC();
            }
            if (!mac && typeof(gSTB) !== 'undefined' && gSTB.GetDeviceMAC) {
                mac = gSTB.GetDeviceMAC();
            }
        } catch(e) {}

        if (mac) {
            setMacAndReload(mac);
        } else {
            showLogin();
        }
    }

    function showLogin() {
        document.getElementById('auto').style.display = 'none';
        document.getElementById('login').style.display = 'block';
        document.getElementById('username').focus();
    }

    function showKeyboard(inputId) {
        var input = document.getElementById(inputId);
        input.focus();
        try {
            if (typeof(gSTB) !== 'undefined' && gSTB.ShowVirtualKeyboard) {
                gSTB.ShowVirtualKeyboard();
            } else if (typeof(stb) !== 'undefined' && stb.ShowVirtualKeyboard) {
                stb.ShowVirtualKeyboard();
            }
        } catch(e) {}
    }

    function doLogin() {
        var user = document.getElementById('username').value;
        var pass = document.getElementById('password').value;
        if (!user) { log('Introduce usuario'); return; }

        log('Verificando...');
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '?type=stb&action=login&login=' + encodeURIComponent(user) + '&password=' + encodeURIComponent(pass), true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState == 4) {
                if (xhr.status == 200) {
                    try {
                        var data = JSON.parse(xhr.responseText);
                        if (data.js && data.js.mac) {
                            setMacAndReload(data.js.mac);
                        } else {
                            log(data.js && data.js.error ? data.js.error : 'Usuario incorrecto');
                        }
                    } catch(e) {
                        log('Error de respuesta');
                    }
                } else {
                    log('Error de conexion');
                }
            }
        };
        xhr.send();
    }

    // Handle remote control navigation
    document.onkeydown = function(e) {
        var key = e.keyCode;
        var focused = document.activeElement;

        if (key == 13) { // OK button
            if (focused.id == 'username') {
                document.getElementById('password').focus();
            } else if (focused.id == 'password') {
                doLogin();
            } else if (focused.tagName == 'BUTTON') {
                focused.click();
            }
        } else if (key == 38) { // Up
            if (focused.id == 'password') document.getElementById('username').focus();
            else if (focused.id == 'loginBtn') document.getElementById('password').focus();
        } else if (key == 40) { // Down
            if (focused.id == 'username') document.getElementById('password').focus();
            else if (focused.id == 'password') document.getElementById('loginBtn').focus();
        }
    };

    window.onload = function() { setTimeout(initApp, 100); };
    </script>
    <style>
        body { background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%); margin: 0; padding: 0; font-family: Arial; min-height: 100vh; }
        .container { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
        h1 { color: #e94560; font-size: 42px; margin-bottom: 5px; }
        h2 { color: #888; font-weight: normal; font-size: 16px; margin-bottom: 40px; }
        #msg { color: #e94560; font-size: 16px; margin: 15px; min-height: 20px; }
        #login { display: none; text-align: center; }
        input { font-size: 20px; padding: 12px 20px; width: 280px; margin: 8px 0; border: 2px solid #333; border-radius: 8px;
                background: #0f0f23; color: #fff; }
        input:focus { outline: none; border-color: #e94560; }
        button { font-size: 18px; padding: 12px 50px; margin-top: 15px; background: #e94560; color: #fff;
                 border: none; border-radius: 8px; cursor: pointer; }
        button:hover, button:focus { background: #ff6b8a; }
    </style>
</head>
<body>
    <div class="container">
        <h1>QuattreTV</h1>
        <h2>IPTV Middleware</h2>

        <div id="auto">
            <p style="color:#888">Conectando...</p>
        </div>

        <div id="login">
            <input type="text" id="username" placeholder="Usuario" onclick="showKeyboard('username')" onfocus="showKeyboard('username')">
            <br>
            <input type="password" id="password" placeholder="Contrasena" onclick="showKeyboard('password')" onfocus="showKeyboard('password')">
            <br>
            <button id="loginBtn" onclick="doLogin()">Entrar</button>
            <div id="msg"></div>
        </div>
    </div>
</body>
</html>'''
    return HttpResponse(html, content_type='text/html')


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def portal_handler(request):
    """
    Main handler for Stalker portal requests.
    Routes to appropriate handler based on 'type' and 'action' params.
    """
    request_type = request.GET.get('type', request.POST.get('type', ''))
    action = request.GET.get('action', request.POST.get('action', ''))

    # If no params, serve appropriate page
    if not request_type and not action:
        if not request.COOKIES.get('mac'):
            return stb_loader_page(request)
        else:
            return stb_portal_app(request)

    # Route to appropriate handler
    handlers = {
        'stb': handle_stb,
        'itv': handle_itv,
        'vod': handle_vod,
        'series': handle_series,
        'epg': handle_epg,
        'tv_archive': handle_tv_archive,
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
    elif action == 'log':
        return stalker_response({'result': True})

    return stalker_response({'error': 'Unknown action'})


def handle_login(request):
    """Handle login with username/password, return device MAC."""
    from django.contrib.auth import authenticate

    username = request.GET.get('login', request.POST.get('login', ''))
    password = request.GET.get('password', request.POST.get('password', ''))

    if not username:
        return stalker_response({'error': 'Usuario requerido'})

    # Authenticate user
    user = authenticate(username=username, password=password)
    if not user:
        # Try without password (some setups don't use password)
        from apps.accounts.models import User
        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return stalker_response({'error': 'Usuario no encontrado'})

    # Get user's first active device
    device = user.devices.filter(is_active=True).first()
    if not device:
        return stalker_response({'error': 'No hay dispositivo asociado'})

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
            'all_modules': ['tv', 'vod', 'epg', 'settings'],
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

    # Get current programs for EPG
    now = timezone.now()
    current_programs = {
        p.channel_id: p for p in Program.objects.filter(
            channel__in=channels,
            start_time__lte=now,
            end_time__gte=now
        )
    }

    data = []
    for ch in channels:
        current = current_programs.get(ch.id)
        data.append({
            'id': str(ch.id),
            'name': ch.name,
            'number': ch.number,
            'cmd': ch.stream_url,
            'logo': ch.logo_display_url,
            'censored': ch.is_adult,
            'hd': 1 if ch.is_hd else 0,
            'fav': 0,  # TODO: Check favorites
            'archive': 1 if ch.has_timeshift else 0,
            'archive_range': ch.timeshift_hours,
            'cur_playing': current.title if current else '',
            'epg_start': current.start_time.isoformat() if current else '',
            'epg_end': current.end_time.isoformat() if current else '',
        })

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
            stream_url = channel.stream_url
        except Channel.DoesNotExist:
            return stalker_response({'error': 'Channel not found'})
    else:
        stream_url = cmd

    # Add authentication token if needed
    if device:
        stream_url = f"{stream_url}?token={device.token}"

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
            't_time': prog.start_time.strftime('%H:%M'),
            't_time_end': prog.end_time.strftime('%H:%M'),
            'name': prog.title,
            'descr': prog.description[:200] if prog.description else '',
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
    category_id = request.GET.get('category')
    page = int(request.GET.get('p', 0))
    per_page = 50

    movies = Movie.objects.filter(is_active=True)

    if category_id and category_id != '*':
        movies = movies.filter(category_id=category_id)

    total = movies.count()
    movies = movies[page * per_page:(page + 1) * per_page]

    data = []
    for movie in movies:
        data.append({
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
            'cmd': movie.stream_url,
        })

    return stalker_response({
        'total_items': total,
        'max_page_items': per_page,
        'data': data,
    })


def handle_vod_link(request):
    """Get VOD stream link."""
    cmd = request.GET.get('cmd', '')
    device = get_device_from_request(request)

    if cmd.isdigit():
        try:
            movie = Movie.objects.get(id=cmd, is_active=True)
            stream_url = movie.stream_url
        except Movie.DoesNotExist:
            return stalker_response({'error': 'Movie not found'})
    else:
        stream_url = cmd

    if device:
        stream_url = f"{stream_url}?token={device.token}"

    return stalker_response({'cmd': stream_url})


# ============== Series Handlers ==============

def handle_series(request, action):
    """Handle Series actions."""
    if action == 'get_categories':
        return handle_vod_categories(request)
    elif action == 'get_ordered_list':
        return handle_series_list(request)

    return stalker_response({'error': 'Unknown action'})


def handle_series_list(request):
    """Get series list."""
    category_id = request.GET.get('category')
    page = int(request.GET.get('p', 0))
    per_page = 50

    series = Series.objects.filter(is_active=True)

    if category_id and category_id != '*':
        series = series.filter(category_id=category_id)

    total = series.count()
    series_list = series[page * per_page:(page + 1) * per_page]

    data = []
    for s in series_list:
        data.append({
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

    data = []
    for prog in programs:
        data.append({
            'id': str(prog.id),
            't_time': prog.start_time.strftime('%H:%M'),
            't_time_end': prog.end_time.strftime('%H:%M'),
            'name': prog.title,
            'descr': prog.description or '',
            'category': prog.category or '',
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
        day_key = prog.start_time.strftime('%Y-%m-%d')
        if day_key not in data:
            data[day_key] = []

        data[day_key].append({
            'id': str(prog.id),
            't_time': prog.start_time.strftime('%H:%M'),
            't_time_end': prog.end_time.strftime('%H:%M'),
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
    """Create timeshift/archive link."""
    cmd = request.GET.get('cmd', '')
    device = get_device_from_request(request)

    # Parse the command - format: "auto /ch/CHANNEL_ID?utc=TIMESTAMP"
    # or just channel_id with utc parameter
    channel_id = request.GET.get('ch_id')
    utc = request.GET.get('utc')

    if not channel_id:
        return stalker_response({'error': 'Channel ID required'})

    try:
        channel = Channel.objects.get(id=channel_id, is_active=True)
    except Channel.DoesNotExist:
        return stalker_response({'error': 'Channel not found'})

    if not channel.has_timeshift:
        return stalker_response({'error': 'Timeshift not available'})

    stream_url = channel.stream_url
    if utc:
        stream_url = f"{stream_url}?utc={utc}"

    if device:
        separator = '&' if '?' in stream_url else '?'
        stream_url = f"{stream_url}{separator}token={device.token}"

    return stalker_response({'cmd': stream_url})


# ============== Other Handlers ==============

def handle_watchdog(request, action):
    """Handle watchdog/keepalive."""
    device = get_device_from_request(request)
    if device:
        device.update_activity(
            ip_address=MACAuthentication.get_client_ip(request)
        )
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
