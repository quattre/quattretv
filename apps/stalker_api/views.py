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
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1920, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>QuattreTV</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0d0d1a; color: #fff; font-family: 'Segoe UI', Tahoma, Arial, sans-serif; width: 1920px; height: 1080px; overflow: hidden; }

        /* Layout principal: sidebar izquierda + video derecha */
        .app { display: flex; width: 1920px; height: 1080px; }

        /* Sidebar */
        .sidebar {
            width: 480px; height: 1080px;
            background: linear-gradient(180deg, #111122 0%, #0a0a18 100%);
            display: flex; flex-direction: column;
            border-right: 1px solid rgba(255,255,255,0.06);
            position: relative; z-index: 10;
        }

        /* Header con logo y reloj */
        .sidebar-header {
            padding: 28px 30px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .sidebar-brand { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 28px; font-weight: 300; letter-spacing: 1px; }
        .logo b { color: #00a651; font-weight: 800; }
        .clock { color: rgba(255,255,255,0.4); font-size: 16px; font-weight: 300; }

        /* Info del canal seleccionado */
        .now-info {
            padding: 18px 30px;
            background: linear-gradient(90deg, rgba(0,166,81,0.12) 0%, transparent 100%);
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .now-channel { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
        .now-channel .ch-num { color: #00a651; margin-right: 8px; }
        .now-epg { color: rgba(255,255,255,0.5); font-size: 14px; }
        .now-badge { display: inline-block; background: #00a651; color: #fff; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-left: 10px; vertical-align: middle; }

        /* Lista de canales */
        .channel-list { flex: 1; overflow: hidden; padding: 8px 0; }
        .ch-item {
            display: flex; align-items: center; padding: 11px 30px; margin: 2px 12px;
            border-radius: 8px; cursor: pointer; transition: all 0.12s;
            border: 1px solid transparent;
        }
        .ch-item:hover { background: rgba(255,255,255,0.04); }
        .ch-item.active {
            background: linear-gradient(90deg, rgba(0,166,81,0.25) 0%, rgba(0,166,81,0.08) 100%);
            border-color: rgba(0,166,81,0.4);
        }
        .ch-item .ch-number {
            width: 36px; font-size: 15px; color: rgba(255,255,255,0.3);
            font-weight: 600; text-align: right; margin-right: 16px;
        }
        .ch-item.active .ch-number { color: #00a651; }
        .ch-logo {
            width: 40px; height: 40px; border-radius: 8px; margin-right: 14px;
            background: rgba(255,255,255,0.06); display: flex; align-items: center;
            justify-content: center; overflow: hidden; flex-shrink: 0;
        }
        .ch-logo img { width: 100%; height: 100%; object-fit: contain; }
        .ch-logo-text { font-size: 11px; color: rgba(255,255,255,0.3); text-align: center; line-height: 1.1; }
        .ch-details { flex: 1; overflow: hidden; }
        .ch-name {
            font-size: 16px; font-weight: 500; white-space: nowrap;
            overflow: hidden; text-overflow: ellipsis;
        }
        .ch-item.active .ch-name { color: #fff; }
        .ch-program {
            font-size: 12px; color: rgba(255,255,255,0.35); margin-top: 2px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .ch-badges { display: flex; gap: 6px; margin-left: 10px; flex-shrink: 0; }
        .badge-hd { background: #2980b9; color: #fff; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 3px; }
        .badge-live { background: #e74c3c; color: #fff; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 3px; }

        /* Footer sidebar */
        .sidebar-footer {
            padding: 16px 30px;
            border-top: 1px solid rgba(255,255,255,0.06);
            display: flex; justify-content: center; gap: 24px;
        }
        .sidebar-footer .key {
            display: inline-flex; align-items: center; gap: 6px;
            color: rgba(255,255,255,0.3); font-size: 12px;
        }
        .sidebar-footer .key kbd {
            background: rgba(255,255,255,0.08); padding: 3px 10px;
            border-radius: 5px; font-family: inherit; font-size: 11px;
            color: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.1);
        }

        /* Area de video */
        .video-area {
            flex: 1; height: 1080px; position: relative; background: #000;
        }
        #html5video {
            width: 100%; height: 100%; object-fit: contain; background: #000;
        }

        /* Overlay de info sobre video (esquina superior) */
        .video-overlay {
            position: absolute; top: 24px; left: 24px; right: 24px;
            display: flex; justify-content: space-between; align-items: flex-start;
            pointer-events: none; z-index: 5;
        }
        .video-tag {
            background: rgba(0,0,0,0.6); backdrop-filter: blur(10px);
            padding: 8px 16px; border-radius: 8px; font-size: 13px;
            color: rgba(255,255,255,0.7);
        }
        .video-tag b { color: #00a651; }
        .video-live {
            background: #e74c3c; padding: 6px 14px; border-radius: 6px;
            font-size: 12px; font-weight: 700; letter-spacing: 1px;
        }

        /* OSD fullscreen */
        #osd {
            display: none; position: fixed; bottom: 0; left: 0; right: 0;
            background: linear-gradient(0deg, rgba(0,0,0,0.9) 0%, transparent 100%);
            padding: 40px 60px; z-index: 20;
        }
        .osd-inner { max-width: 800px; }
        .osd-ch { font-size: 32px; font-weight: 600; margin-bottom: 6px; }
        .osd-ch .osd-num { color: #00a651; margin-right: 10px; }
        .osd-epg { font-size: 18px; color: rgba(255,255,255,0.5); }
        .osd-hint { margin-top: 12px; font-size: 13px; color: rgba(255,255,255,0.25); }

        /* Volumen */
        #vol {
            display: none; position: fixed; top: 50%; right: 60px;
            transform: translateY(-50%); z-index: 30;
            background: rgba(0,0,0,0.8); backdrop-filter: blur(10px);
            padding: 20px 24px; border-radius: 12px; text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .vol-icon { font-size: 24px; margin-bottom: 10px; }
        .vol-bar { width: 6px; height: 150px; background: rgba(255,255,255,0.1); border-radius: 3px; margin: 0 auto; position: relative; }
        .vol-fill { position: absolute; bottom: 0; width: 100%; background: #00a651; border-radius: 3px; transition: height 0.15s; }
        .vol-num { margin-top: 10px; font-size: 16px; font-weight: 600; }

        /* Loading */
        .loading { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; }
        .loading-spinner { width: 40px; height: 40px; border: 3px solid rgba(0,166,81,0.2); border-top-color: #00a651; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { color: rgba(255,255,255,0.4); font-size: 14px; margin-top: 16px; }

        /* Scrollbar oculto */
        .channel-list::-webkit-scrollbar { display: none; }
    </style>
    <script>
    var stbAPI = null, player = null, htmlPlayer = null;
    var channels = [], currentChannel = 0, playingChannelIdx = -1;
    var isFullscreen = false, volume = 50, volTimeout = null, osdTimeout = null;
    var useHTML5 = false, VISIBLE_ITEMS = 12;

    function init() {
        if (typeof gSTB !== "undefined") {
            stbAPI = gSTB;
            try {
                stbAPI.InitPlayer(); stbAPI.SetViewport(0,0,1920,1080);
                stbAPI.SetWinMode(0,1); stbAPI.SetTopWin(1);
                stbAPI.SetTransparentColor(0x000000);
                volume = stbAPI.GetVolume ? stbAPI.GetVolume() : 50;
            } catch(e) {}
        } else if (typeof stb !== "undefined") {
            stbAPI = stb;
            try { volume = stbAPI.GetVolume ? stbAPI.GetVolume() : 50; } catch(e) {}
        }
        if (typeof stbPlayerManager !== "undefined" && stbPlayerManager.list && stbPlayerManager.list[0]) {
            player = stbPlayerManager.list[0];
        }
        if (!stbAPI && !player) {
            useHTML5 = true;
            htmlPlayer = document.getElementById('html5video');
            htmlPlayer.volume = volume / 100;
        }
        updateClock();
        setInterval(updateClock, 30000);
        loadData();
    }

    function updateClock() {
        var el = document.getElementById('clock');
        if (!el) return;
        var d = new Date();
        var h = d.getHours().toString().padStart(2,'0');
        var m = d.getMinutes().toString().padStart(2,'0');
        el.textContent = h + ':' + m;
    }

    function loadData() {
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4 && xhr.status === 200) {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.js && r.js.data) {
                        channels = r.js.data;
                        renderList();
                        updateNowInfo();
                        startPreview();
                    }
                } catch(e) {}
            }
        };
        xhr.open("GET", "?type=itv&action=get_ordered_list&p=0&_t=" + Date.now(), true);
        xhr.send();
    }

    // === Video control ===
    function playChannel(ch) {
        if (useHTML5) {
            var url = ch.cmd.replace('ffmpeg ','').replace('ffrt ','');
            htmlPlayer.src = url;
            htmlPlayer.play().catch(function(e){});
        } else if (player) {
            try { player.play({uri: ch.cmd}); } catch(e) {}
        } else if (stbAPI) {
            try { stbAPI.Play(ch.cmd); } catch(e) {}
        }
    }

    function setViewportPreview() {
        if (useHTML5) {
            htmlPlayer.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#000;';
        } else if (player) {
            try { player.fullscreen=false; player.setViewport({x:480,y:0,width:1440,height:1080}); } catch(e) {}
        } else if (stbAPI) {
            try { stbAPI.SetPIG(0,128,480,0); } catch(e) {}
        }
    }

    function setViewportFullscreen() {
        if (useHTML5) {
            var v = document.getElementById('html5video');
            v.style.cssText = 'position:fixed;top:0;left:0;width:1920px;height:1080px;z-index:0;background:#000;';
        } else if (player) {
            try { player.fullscreen=true; player.setViewport({x:0,y:0,width:1920,height:1080}); } catch(e) {}
        } else if (stbAPI) {
            try { stbAPI.SetPIG(1,256,0,0); } catch(e) {}
        }
    }

    function startPreview() {
        if (channels.length === 0 || isFullscreen) return;
        var ch = channels[currentChannel];
        if (!ch || !ch.cmd) return;
        if (playingChannelIdx === currentChannel) {
            setViewportPreview();
        } else {
            setViewportPreview();
            playChannel(ch);
            playingChannelIdx = currentChannel;
        }
    }

    // === UI rendering ===
    function renderList() {
        var list = document.getElementById('channelList');
        var start = Math.max(0, currentChannel - Math.floor(VISIBLE_ITEMS/2));
        var end = Math.min(channels.length, start + VISIBLE_ITEMS);
        if (end - start < VISIBLE_ITEMS) start = Math.max(0, end - VISIBLE_ITEMS);

        var h = '';
        for (var i = start; i < end; i++) {
            var c = channels[i];
            var cls = (i === currentChannel) ? 'ch-item active' : 'ch-item';
            h += '<div class="' + cls + '">';
            h += '<div class="ch-number">' + c.number + '</div>';
            h += '<div class="ch-logo">';
            if (c.logo) {
                h += '<img src="' + c.logo + '" onerror="this.style.display=\\'none\\';this.nextSibling.style.display=\\'block\\'">';
                h += '<span class="ch-logo-text" style="display:none">' + c.name.substring(0,3) + '</span>';
            } else {
                h += '<span class="ch-logo-text">' + c.name.substring(0,3) + '</span>';
            }
            h += '</div>';
            h += '<div class="ch-details">';
            h += '<div class="ch-name">' + c.name + '</div>';
            if (c.cur_playing) h += '<div class="ch-program">' + c.cur_playing + '</div>';
            h += '</div>';
            h += '<div class="ch-badges">';
            if (c.hd) h += '<span class="badge-hd">HD</span>';
            h += '</div>';
            h += '</div>';
        }
        list.innerHTML = h;
    }

    function updateNowInfo() {
        var ch = channels[currentChannel];
        if (!ch) return;
        var info = document.getElementById('nowInfo');
        var numHtml = '<span class="ch-num">' + ch.number + '</span>' + ch.name;
        if (ch.hd) numHtml += '<span class="now-badge">HD</span>';
        document.getElementById('nowChannel').innerHTML = numHtml;
        document.getElementById('nowEpg').textContent = ch.cur_playing || '';
        // Video overlay
        document.getElementById('videoChName').innerHTML = '<b>' + ch.number + '</b> ' + ch.name;
    }

    // === Fullscreen ===
    function goFullscreen() {
        var ch = channels[currentChannel];
        if (!ch || !ch.cmd) return;
        if (playingChannelIdx !== currentChannel) { playChannel(ch); playingChannelIdx = currentChannel; }
        setViewportFullscreen();
        isFullscreen = true;
        document.getElementById('appContainer').style.display = 'none';
        showOSD();
    }

    function showOSD() {
        var ch = channels[currentChannel];
        if (!ch) return;
        var osd = document.getElementById('osd');
        var numHtml = '<span class="osd-num">' + ch.number + '</span>' + ch.name;
        document.querySelector('.osd-ch').innerHTML = numHtml;
        document.querySelector('.osd-epg').textContent = ch.cur_playing || '';
        osd.style.display = 'block';
        clearTimeout(osdTimeout);
        osdTimeout = setTimeout(function() { osd.style.display = 'none'; }, 4000);
    }

    function showMenu() {
        isFullscreen = false;
        document.getElementById('appContainer').style.display = 'flex';
        document.getElementById('osd').style.display = 'none';
        if (useHTML5) {
            var v = document.getElementById('html5video');
            v.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#000;';
            document.getElementById('videoArea').appendChild(v);
        }
        setViewportPreview();
        renderList();
        updateNowInfo();
    }

    // === Volume ===
    function showVolume() {
        var v = document.getElementById('vol');
        document.querySelector('.vol-fill').style.height = volume + '%';
        document.querySelector('.vol-num').textContent = volume;
        v.style.display = 'block';
        clearTimeout(volTimeout);
        volTimeout = setTimeout(function() { v.style.display = 'none'; }, 2000);
    }

    function adjustVolume(delta) {
        volume = Math.max(0, Math.min(100, volume + delta));
        if (useHTML5 && htmlPlayer) htmlPlayer.volume = volume / 100;
        else if (stbAPI && stbAPI.SetVolume) { try { stbAPI.SetVolume(volume); } catch(e) {} }
        showVolume();
    }

    // === Keys ===
    function handleKey(e) {
        var k = e.keyCode;
        // Volume: + / -
        if (k === 107 || k === 175) { adjustVolume(5); e.preventDefault(); return false; }
        if (k === 109 || k === 174) { adjustVolume(-5); e.preventDefault(); return false; }

        if (isFullscreen) {
            if (k === 38 || k === 33) { // Up / PageUp
                if (currentChannel > 0) {
                    currentChannel--;
                    playChannel(channels[currentChannel]);
                    playingChannelIdx = currentChannel;
                    showOSD();
                }
            } else if (k === 40 || k === 34) { // Down / PageDown
                if (currentChannel < channels.length - 1) {
                    currentChannel++;
                    playChannel(channels[currentChannel]);
                    playingChannelIdx = currentChannel;
                    showOSD();
                }
            } else if (k === 8 || k === 27 || k === 461) { // Back
                showMenu();
            } else if (k === 13) { // OK - show/hide OSD
                var osd = document.getElementById('osd');
                if (osd.style.display === 'none' || !osd.style.display) showOSD();
                else osd.style.display = 'none';
            }
        } else {
            if (k === 38 && currentChannel > 0) {
                currentChannel--;
                renderList(); updateNowInfo(); startPreview();
            } else if (k === 40 && currentChannel < channels.length - 1) {
                currentChannel++;
                renderList(); updateNowInfo(); startPreview();
            } else if (k === 13 && channels.length > 0) {
                goFullscreen();
            }
        }
        e.preventDefault();
        return false;
    }

    document.onkeydown = handleKey;
    window.onload = init;
    </script>
</head>
<body>
    <div class="app" id="appContainer">
        <!-- Sidebar izquierda -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-brand">
                    <div class="logo"><b>Quattre</b>TV</div>
                    <div class="clock" id="clock">--:--</div>
                </div>
            </div>
            <div class="now-info" id="nowInfo">
                <div class="now-channel" id="nowChannel">Cargando...</div>
                <div class="now-epg" id="nowEpg"></div>
            </div>
            <div class="channel-list" id="channelList">
                <div class="loading">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Cargando canales...</div>
                </div>
            </div>
            <div class="sidebar-footer">
                <div class="key"><kbd>OK</kbd> Ver</div>
                <div class="key"><kbd>&#9650;&#9660;</kbd> Navegar</div>
                <div class="key"><kbd>VOL</kbd> Volumen</div>
            </div>
        </div>
        <!-- Area de video -->
        <div class="video-area" id="videoArea">
            <video id="html5video" autoplay playsinline></video>
            <div class="video-overlay">
                <div class="video-tag" id="videoChName"></div>
                <div class="video-live">EN DIRECTO</div>
            </div>
        </div>
    </div>

    <!-- OSD fullscreen -->
    <div id="osd">
        <div class="osd-inner">
            <div class="osd-ch"></div>
            <div class="osd-epg"></div>
            <div class="osd-hint">OK info &middot; &#9650;&#9660; cambiar canal &middot; BACK volver</div>
        </div>
    </div>

    <!-- Volumen -->
    <div id="vol">
        <div class="vol-icon">&#128266;</div>
        <div class="vol-bar"><div class="vol-fill" style="height:50%"></div></div>
        <div class="vol-num">50</div>
    </div>
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
        h1 { color: #00a651; font-size: 42px; margin-bottom: 5px; }
        h2 { color: #888; font-weight: normal; font-size: 16px; margin-bottom: 40px; }
        #msg { color: #00a651; font-size: 16px; margin: 15px; min-height: 20px; }
        #login { display: none; text-align: center; }
        input { font-size: 20px; padding: 12px 20px; width: 280px; margin: 8px 0; border: 2px solid #333; border-radius: 8px;
                background: #0f0f23; color: #fff; }
        input:focus { outline: none; border-color: #00a651; }
        button { font-size: 18px; padding: 12px 50px; margin-top: 15px; background: #00a651; color: #fff;
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
