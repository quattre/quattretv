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
    <script type="text/javascript">
    var stbAPI = null;
    var player = null;
    var channels = [];
    var radios = [];
    var currentList = [];
    var currentIdx = 0;
    var menuIdx = 0;
    var playingIdx = -1;
    var playingType = '';
    var volume = 50;
    var volTimeout = null;
    var screen = 'home'; // home, tv, radio, settings, fullscreen
    var keyLock = false; // bloqueo temporal de teclas

    var menuItems = [
        {id: 'tv', name: 'Television', icon: 'TV'},
        {id: 'radio', name: 'Radio', icon: 'FM'},
        {id: 'settings', name: 'Ajustes', icon: '..'}
    ];

    function init() {
        if (typeof gSTB !== "undefined") {
            stbAPI = gSTB;
            try {
                stbAPI.InitPlayer();
                stbAPI.SetViewport(0, 0, 1920, 1080);
                stbAPI.SetWinMode(0, 1);
                stbAPI.SetTopWin(1);
                stbAPI.SetTransparentColor(0x000000);
                volume = stbAPI.GetVolume ? stbAPI.GetVolume() : 50;
            } catch(err) {}
        } else if (typeof stb !== "undefined") {
            stbAPI = stb;
            try { volume = stbAPI.GetVolume ? stbAPI.GetVolume() : 50; } catch(err) {}
        }
        if (typeof stbPlayerManager !== "undefined" && stbPlayerManager.list && stbPlayerManager.list[0]) {
            player = stbPlayerManager.list[0];
        }
        loadChannels();
        loadRadios();
    }

    function loadChannels() {
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4 && xhr.status === 200) {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.js && r.js.data) {
                        channels = r.js.data;
                        showHome();
                        playBackground();
                    }
                } catch(err) {}
            }
        };
        xhr.open("GET", "?type=itv&action=get_ordered_list&p=0&_t=" + Date.now(), true);
        xhr.send();
    }

    function loadRadios() {
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4 && xhr.status === 200) {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.js && r.js.data) { radios = r.js.data; }
                } catch(err) {}
            }
        };
        xhr.open("GET", "?type=radio&action=get_ordered_list&p=0&_t=" + Date.now(), true);
        xhr.send();
    }

    function playBackground() {
        if (channels.length === 0) return;
        var ch = channels[0];
        if (!ch || !ch.cmd) return;
        if (player) {
            try {
                player.fullscreen = true;
                player.setViewport({x: 0, y: 0, width: 1920, height: 1080});
                player.play({uri: ch.cmd});
            } catch(err) {}
        } else if (stbAPI) {
            try {
                stbAPI.SetPIG(1, 256, 0, 0);
                stbAPI.Play(ch.cmd);
            } catch(err) {}
        }
        playingIdx = 0;
        playingType = 'tv';
        document.body.style.background = "transparent";
    }

    function playItem(item, type) {
        if (!item || !item.cmd) return;
        if (player) {
            try { player.play({uri: item.cmd}); } catch(err) {}
        } else if (stbAPI) {
            try { stbAPI.Play(item.cmd); } catch(err) {}
        }
        playingType = type;
        document.body.style.background = "transparent";
    }

    function showHome() {
        screen = 'home';
        var h = '<div class="overlay">';
        h += '<div class="home-container">';
        h += '<div class="logo">QuattreTV</div>';
        h += '<div class="menu-grid">';
        for (var i = 0; i < menuItems.length; i++) {
            var m = menuItems[i];
            var cls = (i === menuIdx) ? 'menu-item sel' : 'menu-item';
            h += '<div class="' + cls + '">';
            h += '<div class="menu-icon">' + m.icon + '</div>';
            h += '<div class="menu-name">' + m.name + '</div>';
            h += '</div>';
        }
        h += '</div>';
        h += '<div class="home-info">';
        h += '<span>Canales: ' + channels.length + '</span>';
        h += '<span>Radio: ' + radios.length + '</span>';
        h += '</div>';
        h += '<div class="help">OK=Seleccionar  Flechas=Navegar</div>';
        h += '</div></div>';
        document.getElementById("content").innerHTML = h;
        document.getElementById("content").style.display = "block";
    }

    function showTV() {
        screen = 'tv';
        currentList = channels;
        showList('Television', 'tv');
    }

    function showRadio() {
        screen = 'radio';
        currentList = radios;
        showList('Radio', 'radio');
    }

    function showList(title, type) {
        var h = '<div class="overlay">';
        h += '<div class="list-container">';
        h += '<div class="list-header">';
        h += '<span class="back-arrow">&#9664;</span>';
        h += '<span class="list-title">' + title + '</span>';
        h += '<span class="list-count">' + currentList.length + '</span>';
        h += '</div>';
        h += '<div class="list-items">';
        var start = Math.max(0, currentIdx - 4);
        var end = Math.min(currentList.length, start + 9);
        for (var i = start; i < end; i++) {
            var c = currentList[i];
            var cls = (i === currentIdx) ? 'list-item sel' : 'list-item';
            var playing = (playingIdx === i && playingType === type) ? ' playing' : '';
            h += '<div class="' + cls + playing + '">';
            h += '<span class="item-num">' + c.number + '</span>';
            h += '<span class="item-name">' + c.name + '</span>';
            if (c.hd) h += '<span class="badge">HD</span>';
            if (playingIdx === i && playingType === type) h += '<span class="now-playing">&#9654;</span>';
            h += '</div>';
        }
        h += '</div>';
        h += '<div class="help">OK=Ver  Back=Menu  Flechas=Navegar</div>';
        h += '</div></div>';
        document.getElementById("content").innerHTML = h;
    }

    function showSettings() {
        screen = 'settings';
        var h = '<div class="overlay">';
        h += '<div class="settings-container">';
        h += '<div class="list-header">';
        h += '<span class="back-arrow">&#9664;</span>';
        h += '<span class="list-title">Ajustes</span>';
        h += '</div>';
        h += '<div class="settings-info">';
        h += '<div class="setting-row"><span>Version:</span><span>QuattreTV 1.0</span></div>';
        h += '<div class="setting-row"><span>Canales:</span><span>' + channels.length + '</span></div>';
        h += '<div class="setting-row"><span>Radio:</span><span>' + radios.length + '</span></div>';
        h += '<div class="setting-row"><span>Volumen:</span><span>' + volume + '%</span></div>';
        h += '</div>';
        h += '<div class="help">Back=Menu</div>';
        h += '</div></div>';
        document.getElementById("content").innerHTML = h;
    }

    function goFullscreen() {
        screen = 'fullscreen';
        document.getElementById("content").style.display = "none";
        var item = currentList[currentIdx];
        if (item) {
            document.getElementById("osd").innerHTML = item.number + '. ' + item.name;
            document.getElementById("osd").style.display = "block";
            setTimeout(function() { document.getElementById("osd").style.display = "none"; }, 3000);
        }
    }

    function showVolume() {
        var v = document.getElementById("vol");
        v.innerHTML = "Vol: " + volume;
        v.style.display = "block";
        clearTimeout(volTimeout);
        volTimeout = setTimeout(function() { v.style.display = "none"; }, 2000);
    }

    function adjustVolume(delta) {
        volume = Math.max(0, Math.min(100, volume + delta));
        if (stbAPI && stbAPI.SetVolume) {
            try { stbAPI.SetVolume(volume); } catch(err) {}
        }
        showVolume();
    }

    function lockKeys() {
        keyLock = true;
        setTimeout(function() { keyLock = false; }, 300);
    }

    function handleKey(e) {
        var k = e.keyCode;
        e.preventDefault();

        // Volumen siempre disponible
        if (k === 107) { adjustVolume(5); return false; }
        if (k === 109) { adjustVolume(-5); return false; }

        // Ignorar teclas si están bloqueadas
        if (keyLock) return false;

        if (screen === 'fullscreen') {
            if (k === 38 || k === 33) { // Up - canal anterior
                if (currentIdx > 0) {
                    currentIdx--;
                    playingIdx = currentIdx;
                    playItem(currentList[currentIdx], playingType);
                    document.getElementById("osd").innerHTML = currentList[currentIdx].number + '. ' + currentList[currentIdx].name;
                    document.getElementById("osd").style.display = "block";
                    setTimeout(function() { document.getElementById("osd").style.display = "none"; }, 3000);
                }
            } else if (k === 40 || k === 34) { // Down - canal siguiente
                if (currentIdx < currentList.length - 1) {
                    currentIdx++;
                    playingIdx = currentIdx;
                    playItem(currentList[currentIdx], playingType);
                    document.getElementById("osd").innerHTML = currentList[currentIdx].number + '. ' + currentList[currentIdx].name;
                    document.getElementById("osd").style.display = "block";
                    setTimeout(function() { document.getElementById("osd").style.display = "none"; }, 3000);
                }
            } else if (k === 8 || k === 27) { // Back - volver a lista (sin OK)
                lockKeys();
                document.getElementById("content").style.display = "block";
                document.getElementById("osd").style.display = "none";
                if (playingType === 'tv') showTV();
                else if (playingType === 'radio') showRadio();
                else showHome();
            }
        } else if (screen === 'home') {
            if (k === 37 && menuIdx > 0) { // Left
                menuIdx--;
                showHome();
            } else if (k === 39 && menuIdx < menuItems.length - 1) { // Right
                menuIdx++;
                showHome();
            } else if (k === 13) { // OK
                lockKeys();
                var sel = menuItems[menuIdx].id;
                if (sel === 'tv') showTV();
                else if (sel === 'radio') showRadio();
                else if (sel === 'settings') showSettings();
            }
        } else if (screen === 'tv' || screen === 'radio') {
            var type = screen;
            if (k === 38 && currentIdx > 0) { // Up
                currentIdx--;
                playingIdx = currentIdx;
                playItem(currentList[currentIdx], type);
                showList(type === 'tv' ? 'Television' : 'Radio', type);
            } else if (k === 40 && currentIdx < currentList.length - 1) { // Down
                currentIdx++;
                playingIdx = currentIdx;
                playItem(currentList[currentIdx], type);
                showList(type === 'tv' ? 'Television' : 'Radio', type);
            } else if (k === 13) { // OK - fullscreen
                lockKeys();
                goFullscreen();
            } else if (k === 8 || k === 27) { // Back
                lockKeys();
                currentIdx = 0;
                showHome();
            }
        } else if (screen === 'settings') {
            if (k === 8 || k === 27) { // Back
                lockKeys();
                showHome();
            }
        }
        return false;
    }

    document.onkeydown = handleKey;
    window.onload = init;
    </script>
    <style>
        * { box-sizing: border-box; }
        body { background: transparent; color: #fff; font-family: 'Arial', sans-serif; margin: 0; padding: 0; overflow: hidden; }

        .overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: linear-gradient(135deg, rgba(10,10,30,0.85) 0%, rgba(20,20,50,0.75) 100%);
            display: flex; align-items: center; justify-content: center;
        }

        .home-container { text-align: center; }
        .logo { font-size: 72px; font-weight: bold; color: #e94560; margin-bottom: 60px; text-shadow: 0 0 30px rgba(233,69,96,0.5); }

        .menu-grid { display: flex; gap: 40px; justify-content: center; margin-bottom: 60px; }
        .menu-item {
            width: 200px; height: 180px; background: rgba(255,255,255,0.1);
            border-radius: 20px; display: flex; flex-direction: column;
            align-items: center; justify-content: center; cursor: pointer;
            border: 3px solid transparent; transition: all 0.2s;
        }
        .menu-item.sel { background: rgba(233,69,96,0.3); border-color: #e94560; transform: scale(1.1); }
        .menu-icon { font-size: 48px; margin-bottom: 15px; }
        .menu-name { font-size: 24px; }

        .home-info { color: #888; font-size: 18px; margin-bottom: 30px; }
        .home-info span { margin: 0 20px; }

        .list-container { width: 600px; }
        .list-header { display: flex; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid rgba(255,255,255,0.2); }
        .back-arrow { font-size: 24px; margin-right: 15px; color: #e94560; }
        .list-title { font-size: 32px; font-weight: bold; flex: 1; }
        .list-count { background: #e94560; padding: 5px 15px; border-radius: 20px; font-size: 18px; }

        .list-items { max-height: 600px; }
        .list-item {
            display: flex; align-items: center; padding: 15px 20px;
            background: rgba(255,255,255,0.05); margin: 5px 0; border-radius: 10px;
            border: 2px solid transparent;
        }
        .list-item.sel { background: rgba(233,69,96,0.3); border-color: #e94560; }
        .list-item.playing { background: rgba(46,204,113,0.2); }
        .item-num { width: 50px; color: #888; font-size: 18px; }
        .item-name { flex: 1; font-size: 22px; }
        .badge { background: #3498db; padding: 3px 8px; border-radius: 5px; font-size: 12px; margin-left: 10px; }
        .now-playing { color: #2ecc71; margin-left: 10px; }

        .settings-container { width: 500px; }
        .settings-info { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 30px; }
        .setting-row { display: flex; justify-content: space-between; padding: 15px 0; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 22px; }
        .setting-row:last-child { border: none; }

        .help { color: #666; font-size: 16px; margin-top: 30px; text-align: center; }

        #osd {
            display: none; position: fixed; bottom: 80px; left: 80px;
            background: rgba(0,0,0,0.85); padding: 20px 40px;
            font-size: 28px; border-radius: 10px;
            border-left: 5px solid #e94560;
        }
        #vol {
            display: none; position: fixed; top: 50%; left: 50%;
            transform: translate(-50%,-50%); background: rgba(0,0,0,0.9);
            padding: 25px 50px; font-size: 28px; border-radius: 15px;
        }
    </style>
</head>
<body>
    <div id="content"></div>
    <div id="osd"></div>
    <div id="vol"></div>
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
