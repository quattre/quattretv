"""
Stalker Portal compatible API views.
"""
import hashlib
import time
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, authentication_classes
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>QuattreTV</title>
    <script type="text/javascript">
    var stbAPI = null;
    var player = null;
    var htmlPlayer = null; // video HTML5 para LG/navegadores
    var channels = [];
    var currentChannel = 0;
    var playingChannelIdx = -1;
    var isFullscreen = false;
    var volume = 50;
    var volTimeout = null;
    var useHTML5 = false;
    var view = "list";          // list | guide | recordings
    var guide = [];
    var guideIdx = 0;
    var guideChannel = null;
    var recordings = [];
    var recIdx = 0;
    var toastTimeout = null;

    function fitScreen() {
        // El surface de la app webOS ya es 1920x1080, no hace falta escalar.
        // Un transform CSS en un ancestro rompe el plano de video por hardware
        // del TV (la vista previa desaparece), por eso NO se aplica transform.
    }

    function init() {
        fitScreen();
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

        // Try to get stbPlayerManager
        if (typeof stbPlayerManager !== "undefined" && stbPlayerManager.list && stbPlayerManager.list[0]) {
            player = stbPlayerManager.list[0];
        }

        // Si no hay API de STB, usar video HTML5
        if (!stbAPI && !player) {
            useHTML5 = true;
            htmlPlayer = document.getElementById('html5video');
            htmlPlayer.style.display = 'block';
            htmlPlayer.volume = volume / 100;
            // El archivo y las grabaciones se sirven como MPEG-TS crudo: el
            // deco lo reproduce, pero el <video> de LG no. Avisar en vez de
            // quedarse en negro.
            htmlPlayer.onerror = function() {
                toast('Este contenido no se puede reproducir en este dispositivo');
            };
        }

        loadData();
    }

    function api(query, cb) {
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    try {
                        var r = JSON.parse(xhr.responseText);
                        cb(r.js || {});
                        return;
                    } catch(err) {}
                }
                cb(null);
            }
        };
        xhr.open("GET", "?" + query + "&_t=" + Date.now(), true);
        xhr.send();
    }

    function loadData() {
        loadPage(0);
    }

    // El listado va paginado de 50 en 50: antes solo se pedia la primera
    // pagina, asi que en la tele solo se veian 50 canales.
    function loadPage(page) {
        api("type=itv&action=get_ordered_list&p=" + page, function(js) {
            if (!js || !js.data) return;
            channels = channels.concat(js.data);
            if (page === 0) {
                showChannels();
                startPreview();
            } else {
                if (view === "list") showChannels();
            }
            var perPage = js.max_page_items || 50;
            if (channels.length < (js.total_items || 0) && js.data.length >= perPage) {
                loadPage(page + 1);
            }
        });
    }

    function setViewportPreview() {
        if (useHTML5) {
            htmlPlayer.style.cssText = 'position:fixed;top:120px;left:730px;width:1120px;height:630px;z-index:2;border-radius:18px;';
        } else if (player) {
            try {
                player.fullscreen = false;
                player.aspectConversion = 1;
                player.setViewport({x: 730, y: 120, width: 1120, height: 630});
            } catch(err) {}
        } else if (stbAPI) {
            try { stbAPI.SetPIG(0, 128, 730, 120); } catch(err) {}
        }
    }

    function setViewportFullscreen() {
        if (useHTML5) {
            htmlPlayer.style.cssText = 'position:fixed;top:0;left:0;width:1920px;height:1080px;z-index:0;';
        } else if (player) {
            try {
                player.fullscreen = true;
                player.setViewport({x: 0, y: 0, width: 1920, height: 1080});
            } catch(err) {}
        } else if (stbAPI) {
            try { stbAPI.SetPIG(1, 256, 0, 0); } catch(err) {}
        }
    }

    function playChannel(ch) {
        if (useHTML5) {
            var url = ch.cmd.replace('ffmpeg ', '').replace('ffrt ', '');
            htmlPlayer.src = url;
            htmlPlayer.play().catch(function(e) { console.log('Play error:', e); });
        } else if (player) {
            try { player.play({uri: ch.cmd}); } catch(err) {}
        } else if (stbAPI) {
            try { stbAPI.Play(ch.cmd); } catch(err) {}
        }
        document.body.style.background = "transparent";
    }

    function startPreview() {
        if (channels.length === 0 || isFullscreen) return;
        var ch = channels[currentChannel];
        if (!ch || !ch.cmd) return;

        // Si ya está reproduciendo el mismo canal, solo cambiar viewport
        if (playingChannelIdx === currentChannel) {
            setViewportPreview();
        } else {
            // Cambiar de canal
            setViewportPreview();
            playChannel(ch);
            playingChannelIdx = currentChannel;
        }
    }

    function esc(s) {
        if (s === undefined || s === null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function showChannels() {
        view = "list";
        var ch = channels[currentChannel];
        var h = '<div class="panel">';
        h += '<div class="header"><div class="logo">Quattre<span>TV</span></div>';
        h += '<div class="counter">' + channels.length + ' canales</div></div>';

        h += '<div class="list">';
        var visible = 11;
        var start = Math.max(0, currentChannel - 5);
        var end = Math.min(channels.length, start + visible);
        if (end - start < visible) start = Math.max(0, end - visible);
        for (var i = start; i < end; i++) {
            var c = channels[i];
            var cls = (i === currentChannel) ? "item sel" : "item";
            h += '<div class="' + cls + '">';
            h += '<div class="num">' + c.number + '</div>';
            h += '<div class="info"><div class="name">' + esc(c.name);
            if (c.hd) h += ' <span class="hd">HD</span>';
            if (c.fav) h += ' <span class="fav">★</span>';
            if (c.archive) h += ' <span class="arch">⟲</span>';
            h += '</div>';
            if (c.cur_playing) {
                h += '<div class="epg">' + esc(c.cur_playing);
                if (c.epg_cur_end) h += ' <span class="t">hasta ' + esc(c.epg_cur_end) + '</span>';
                h += '</div>';
                h += '<div class="bar"><i style="width:' + (c.epg_progress || 0) + '%"></i></div>';
            }
            h += '</div></div>';
        }
        h += '</div>';

        h += '<div class="help"><span>OK</span> Ver <span>▶</span> Guia <span>REC</span> Grabar <span>VERDE</span> Grabaciones</div>';
        h += '</div>';
        document.getElementById("content").innerHTML = h;
        updatePreviewCap(ch);
    }

    function toast(msg) {
        var t = document.getElementById("toast");
        t.innerHTML = esc(msg);
        t.style.display = "block";
        clearTimeout(toastTimeout);
        toastTimeout = setTimeout(function() { t.style.display = "none"; }, 2500);
    }

    // ---------- Guia de programacion ----------

    function openGuide() {
        var ch = channels[currentChannel];
        if (!ch) return;
        guideChannel = ch;
        guide = [];
        guideIdx = 0;
        view = "guide";
        document.getElementById("content").innerHTML =
            '<div class="panel"><div class="header"><div class="logo">Guia</div></div>' +
            '<div style="color:#666;padding:20px;">Cargando programacion...</div></div>';
        api("type=epg&action=get_simple_data_table&ch_id=" + ch.id, function(js) {
            if (view !== "guide") return;
            guide = (js && js.data) ? js.data : [];
            for (var i = 0; i < guide.length; i++) {
                if (guide[i].current) { guideIdx = i; break; }
            }
            renderGuide();
        });
    }

    function renderGuide() {
        var h = '<div class="panel">';
        h += '<div class="header"><div class="logo">' + esc(guideChannel.name) + '</div>';
        h += '<div class="counter">Guia</div></div>';

        if (guide.length === 0) {
            h += '<div class="list"><div style="color:#666;padding:20px;">Sin datos de EPG para este canal</div></div>';
        } else {
            h += '<div class="list">';
            var visible = 9;
            var start = Math.max(0, guideIdx - 4);
            var end = Math.min(guide.length, start + visible);
            if (end - start < visible) start = Math.max(0, end - visible);
            for (var i = start; i < end; i++) {
                var p = guide[i];
                var cls = (i === guideIdx) ? "item sel" : "item";
                if (p.past) cls += " past";
                h += '<div class="' + cls + '">';
                h += '<div class="num sm">' + esc(p.t_time) + '</div>';
                h += '<div class="info"><div class="name">' + esc(p.name);
                if (p.rec) h += ' <span class="rec">REC</span>';
                if (p.current) h += ' <span class="live">AHORA</span>';
                h += '</div>';
                if (p.current) h += '<div class="bar"><i style="width:' + (p.progress || 0) + '%"></i></div>';
                h += '</div></div>';
            }
            h += '</div>';

            var sel = guide[guideIdx];
            if (sel && sel.descr) {
                h += '<div class="descr">' + esc(sel.descr.substring(0, 220)) + '</div>';
            }
        }

        var hint = guide.length && guide[guideIdx] && guide[guideIdx].past
            ? '<span>OK</span> Ver desde el archivo' : '<span>REC</span> Grabar';
        h += '<div class="help">' + hint + ' <span>◀</span> Volver</div>';
        h += '</div>';
        document.getElementById("content").innerHTML = h;
    }

    function guideAction() {
        var p = guide[guideIdx];
        if (!p) return;
        if (p.past) {
            playCatchup(p);
        } else {
            recordProgram(p);
        }
    }

    function recordProgram(p) {
        if (!p) return;
        api("type=pvr&action=create_task&program_id=" + p.id, function(js) {
            if (js && js.result) {
                p.rec = 1;
                toast('Grabacion programada: ' + p.name);
                if (view === "guide") renderGuide();
            } else {
                toast((js && js.error) ? js.error : 'No se pudo programar');
            }
        });
    }

    function playCatchup(p) {
        if (!guideChannel.archive) { toast('Este canal no tiene archivo'); return; }
        api("type=tv_archive&action=create_link&ch_id=" + guideChannel.id +
            "&utc=" + p.start_timestamp + "&lutc=" + p.stop_timestamp, function(js) {
            if (js && js.cmd) {
                playChannel({cmd: js.cmd});
                playingChannelIdx = -1;
                setViewportFullscreen();
                isFullscreen = true;
                document.getElementById("content").style.display = "none";
                document.getElementById("preview").style.display = "none";
                document.getElementById("preview-cap").style.display = "none";
                document.getElementById("osd").style.display = "block";
                document.getElementById("osd").innerHTML =
                    '<div class="osd-ch">' + esc(guideChannel.name) + ' · archivo</div>' +
                    '<div class="osd-epg">' + esc(p.name) + '</div>';
            } else {
                toast((js && js.error) ? js.error : 'Archivo no disponible');
            }
        });
    }

    // ---------- Grabaciones ----------

    function openRecordings() {
        view = "recordings";
        recIdx = 0;
        document.getElementById("content").innerHTML =
            '<div class="panel"><div class="header"><div class="logo">Grabaciones</div></div>' +
            '<div style="color:#666;padding:20px;">Cargando...</div></div>';
        api("type=pvr&action=get_ordered_list", function(js) {
            if (view !== "recordings") return;
            recordings = (js && js.data) ? js.data : [];
            renderRecordings((js && js.error) ? js.error : null);
        });
    }

    function renderRecordings(error) {
        var h = '<div class="panel">';
        h += '<div class="header"><div class="logo">Grabaciones</div>';
        h += '<div class="counter">' + recordings.length + '</div></div>';
        h += '<div class="list">';
        if (error) {
            h += '<div style="color:#666;padding:20px;">' + esc(error) + '</div>';
        } else if (recordings.length === 0) {
            h += '<div style="color:#666;padding:20px;">Todavia no hay grabaciones</div>';
        } else {
            var visible = 11;
            var start = Math.max(0, recIdx - 5);
            var end = Math.min(recordings.length, start + visible);
            if (end - start < visible) start = Math.max(0, end - visible);
            for (var i = start; i < end; i++) {
                var r = recordings[i];
                var cls = (i === recIdx) ? "item sel" : "item";
                h += '<div class="' + cls + '">';
                h += '<div class="num sm">' + esc(r.start_time.substring(11)) + '</div>';
                h += '<div class="info"><div class="name">' + esc(r.name);
                h += ' <span class="st ' + esc(r.status) + '">' + esc(statusLabel(r.status)) + '</span></div>';
                h += '<div class="epg">' + esc(r.ch_name) + ' · ' + esc(r.start_time) + '</div>';
                h += '</div></div>';
            }
        }
        h += '</div>';
        h += '<div class="help"><span>OK</span> Ver <span>REC</span> Borrar <span>◀</span> Volver</div>';
        h += '</div>';
        document.getElementById("content").innerHTML = h;
    }

    function statusLabel(s) {
        if (s === 'completed') return 'LISTA';
        if (s === 'recording') return 'GRABANDO';
        if (s === 'scheduled') return 'PROGRAMADA';
        if (s === 'failed') return 'ERROR';
        return s;
    }

    function playRecording() {
        var r = recordings[recIdx];
        if (!r) return;
        if (r.status !== 'completed') { toast('La grabacion aun no esta lista'); return; }
        api("type=pvr&action=create_link&cmd=" + r.id, function(js) {
            if (js && js.cmd) {
                playChannel({cmd: js.cmd});
                playingChannelIdx = -1;
                setViewportFullscreen();
                isFullscreen = true;
                document.getElementById("content").style.display = "none";
                document.getElementById("preview").style.display = "none";
                document.getElementById("preview-cap").style.display = "none";
                document.getElementById("osd").style.display = "block";
                document.getElementById("osd").innerHTML =
                    '<div class="osd-ch">Grabacion</div>' +
                    '<div class="osd-epg">' + esc(r.name) + '</div>';
            } else {
                toast((js && js.error) ? js.error : 'No se pudo reproducir');
            }
        });
    }

    function deleteRecording() {
        var r = recordings[recIdx];
        if (!r) return;
        api("type=pvr&action=delete_task&id=" + r.id, function(js) {
            if (js && js.result) {
                recordings.splice(recIdx, 1);
                if (recIdx >= recordings.length) recIdx = Math.max(0, recordings.length - 1);
                toast('Grabacion borrada');
                renderRecordings(null);
            } else {
                toast((js && js.error) ? js.error : 'No se pudo borrar');
            }
        });
    }

    function recordCurrent() {
        var ch = channels[currentChannel];
        if (!ch) return;
        api("type=itv&action=get_short_epg&ch_id=" + ch.id, function(js) {
            var list = (js && js.data) ? js.data : [];
            if (list.length === 0) { toast('Sin EPG para grabar este canal'); return; }
            recordProgram(list[0]);
        });
    }

    function updatePreviewCap(ch) {
        var cap = document.getElementById("preview-cap");
        if (!cap || !ch) return;
        var html = '<div class="t">' + ch.number + '. ' + esc(ch.name) + '</div>';
        if (ch.cur_playing) {
            html += '<div class="e">' + esc(ch.epg_cur_start) + ' - ' + esc(ch.epg_cur_end) +
                    '  ' + esc(ch.cur_playing) + '</div>';
            html += '<div class="bar" style="width:520px;"><i style="width:' +
                    (ch.epg_progress || 0) + '%"></i></div>';
        }
        if (ch.epg_next) {
            html += '<div class="e">Despues: ' + esc(ch.epg_next_start) + ' ' + esc(ch.epg_next) + '</div>';
        }
        cap.innerHTML = html;
    }

    function osdFor(ch) {
        var html = '<div class="osd-ch">' + ch.number + '. ' + esc(ch.name) + '</div>';
        if (ch.cur_playing) {
            html += '<div class="osd-epg">' + esc(ch.epg_cur_start) + ' - ' + esc(ch.epg_cur_end) +
                    '  ' + esc(ch.cur_playing) + '</div>';
            html += '<div class="bar"><i style="width:' + (ch.epg_progress || 0) + '%"></i></div>';
        }
        if (ch.epg_next) {
            html += '<div class="osd-epg">Despues: ' + esc(ch.epg_next_start) + ' ' + esc(ch.epg_next) + '</div>';
        }
        return html;
    }

    function goFullscreen() {
        var ch = channels[currentChannel];
        if (!ch || !ch.cmd) return;

        // Si ya está reproduciendo este canal, solo cambiar viewport
        if (playingChannelIdx === currentChannel) {
            setViewportFullscreen();
        } else {
            // Nuevo canal, reproducir
            setViewportFullscreen();
            playChannel(ch);
            playingChannelIdx = currentChannel;
        }

        isFullscreen = true;
        document.getElementById("content").style.display = "none";
        document.getElementById("preview").style.display = "none";
        document.getElementById("preview-cap").style.display = "none";
        document.getElementById("osd").style.display = "block";
        document.getElementById("osd").innerHTML = osdFor(ch);
    }

    function showMenu() {
        // Volver al menu sin parar reproduccion, solo cambiar viewport
        setViewportPreview();
        isFullscreen = false;
        document.getElementById("content").style.display = "block";
        document.getElementById("preview").style.display = "flex";
        document.getElementById("preview-cap").style.display = "block";
        document.getElementById("osd").style.display = "none";
        showChannels();
        // Si veniamos del archivo o de una grabacion, el canal ya no suena.
        if (playingChannelIdx === -1) startPreview();
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
        if (useHTML5 && htmlPlayer) {
            htmlPlayer.volume = volume / 100;
        } else if (stbAPI && stbAPI.SetVolume) {
            try { stbAPI.SetVolume(volume); } catch(err) {}
        }
        showVolume();
    }

    function handleKey(e) {
        var k = e.keyCode;
        if (k === 107) { adjustVolume(5); return false; }
        if (k === 109) { adjustVolume(-5); return false; }
        if (isFullscreen) {
            if (k === 38 || k === 33) {
                // Cambiar canal en fullscreen
                if (currentChannel > 0) {
                    currentChannel--;
                    var ch = channels[currentChannel];
                    playChannel(ch);
                    playingChannelIdx = currentChannel;
                    document.getElementById("osd").innerHTML = osdFor(ch);
                }
            } else if (k === 40 || k === 34) {
                if (currentChannel < channels.length - 1) {
                    currentChannel++;
                    var ch = channels[currentChannel];
                    playChannel(ch);
                    playingChannelIdx = currentChannel;
                    document.getElementById("osd").innerHTML = osdFor(ch);
                }
            } else if (k === 8 || k === 27 || k === 13) {
                showMenu();
            }
        } else if (view === "guide") {
            if (k === 38 && guideIdx > 0) {
                guideIdx--;
                renderGuide();
            } else if (k === 40 && guideIdx < guide.length - 1) {
                guideIdx++;
                renderGuide();
            } else if (k === 13) {
                guideAction();
            } else if (k === 82 || k === 112) {
                recordProgram(guide[guideIdx]);
            } else if (k === 37 || k === 8 || k === 27) {
                showChannels();
            }
        } else if (view === "recordings") {
            if (k === 38 && recIdx > 0) {
                recIdx--;
                renderRecordings(null);
            } else if (k === 40 && recIdx < recordings.length - 1) {
                recIdx++;
                renderRecordings(null);
            } else if (k === 13) {
                playRecording();
            } else if (k === 82 || k === 112) {
                deleteRecording();
            } else if (k === 37 || k === 8 || k === 27) {
                showChannels();
            }
        } else {
            if (k === 38 && currentChannel > 0) {
                currentChannel--;
                showChannels();
                startPreview();
            } else if (k === 40 && currentChannel < channels.length - 1) {
                currentChannel++;
                showChannels();
                startPreview();
            } else if (k === 13 && channels.length > 0) {
                goFullscreen();
            } else if (k === 39 && channels.length > 0) {
                openGuide();
            } else if (k === 82 || k === 112) {
                recordCurrent();
            } else if (k === 113 || k === 83) {
                openRecordings();
            }
        }
        return false;
    }

    document.onkeydown = handleKey;
    window.onresize = fitScreen;
    window.onload = init;
    </script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { width: 100%; height: 100%; overflow: hidden; }
        body { background: #0a0a1a; color: #fff; font-family: 'Segoe UI', Arial, sans-serif; }

        .panel {
            position: fixed; top: 36px; left: 36px; width: 640px; height: 1008px;
            display: flex; flex-direction: column;
            background: linear-gradient(180deg, rgba(15,15,35,0.95) 0%, rgba(10,10,25,0.9) 100%);
            border-radius: 18px; padding: 30px; border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }

        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding-bottom: 18px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .logo { font-size: 40px; font-weight: 300; color: #fff; }
        .logo span { color: #00a651; font-weight: 700; }
        .counter { background: rgba(0,166,81,0.2); color: #00a651; padding: 8px 16px; border-radius: 20px; font-size: 18px; }

        .list { flex: 1; overflow: hidden; margin-bottom: 16px; }
        .item { display: flex; align-items: center; padding: 15px 18px; margin: 6px 0; border-radius: 12px; background: rgba(255,255,255,0.03); border: 2px solid transparent; transition: all 0.15s; }
        .item.sel { background: linear-gradient(90deg, rgba(0,166,81,0.3) 0%, rgba(0,166,81,0.1) 100%); border-color: #00a651; }
        .num { width: 58px; font-size: 24px; color: #666; font-weight: 600; }
        .item.sel .num { color: #00a651; }
        .info { flex: 1; overflow: hidden; }
        .name { font-size: 24px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .hd { background: #3498db; color: #fff; font-size: 12px; padding: 2px 7px; border-radius: 4px; margin-left: 8px; font-weight: 700; }
        .epg { font-size: 16px; color: #888; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        .num.sm { font-size: 20px; width: 78px; color: #7a8; }
        .fav { color: #f1c40f; font-size: 18px; margin-left: 6px; }
        .arch { color: #3498db; font-size: 18px; margin-left: 6px; }
        .rec { background: #e74c3c; color: #fff; font-size: 12px; padding: 2px 7px; border-radius: 4px; margin-left: 8px; font-weight: 700; }
        .live { background: #00a651; color: #fff; font-size: 12px; padding: 2px 7px; border-radius: 4px; margin-left: 8px; font-weight: 700; }
        .item.past { opacity: 0.55; }
        .epg .t { color: #667; }
        .bar { height: 4px; background: rgba(255,255,255,0.12); border-radius: 2px; margin-top: 8px; overflow: hidden; }
        .bar i { display: block; height: 100%; background: #00a651; }
        .descr { color: #99a; font-size: 17px; line-height: 1.45; padding: 14px 4px 16px; border-top: 1px solid rgba(255,255,255,0.08); }
        .st { font-size: 12px; padding: 2px 7px; border-radius: 4px; margin-left: 8px; font-weight: 700; background: #555; color: #fff; }
        .st.completed { background: #00a651; }
        .st.recording { background: #e74c3c; }
        .st.scheduled { background: #3498db; }
        .st.failed { background: #7f8c8d; }

        #toast {
            display: none; position: fixed; bottom: 60px; left: 50%;
            transform: translateX(-50%); z-index: 30;
            background: linear-gradient(180deg, rgba(15,15,35,0.97) 0%, rgba(10,10,25,0.95) 100%);
            padding: 18px 34px; font-size: 22px; border-radius: 12px;
            border-left: 4px solid #00a651;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }

        .help { text-align: center; color: #555; font-size: 15px; }
        .help span { background: rgba(255,255,255,0.1); padding: 5px 12px; border-radius: 6px; margin: 0 5px; color: #888; }

        #preview { position: fixed; top: 120px; left: 730px; width: 1120px; height: 630px;
            border-radius: 18px; border: 2px solid rgba(0,166,81,0.4); background: transparent;
            z-index: 1; overflow: hidden;
            display: flex; align-items: center; justify-content: center; color: #444; font-size: 28px; }
        #preview-cap { position: fixed; top: 772px; left: 730px; width: 1120px; z-index: 2; }
        #preview-cap .t { font-size: 34px; font-weight: 600; }
        #preview-cap .e { font-size: 20px; color: #9aa; margin-top: 8px; }

        #osd {
            display: none; position: fixed; bottom: 60px; left: 60px;
            background: linear-gradient(180deg, rgba(15,15,35,0.95) 0%, rgba(10,10,25,0.9) 100%);
            padding: 20px 30px; border-radius: 12px;
            border-left: 4px solid #00a651; min-width: 350px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }
        .osd-ch { font-size: 26px; font-weight: 600; }
        .osd-epg { font-size: 16px; color: #aaa; margin-top: 8px; }

        #vol {
            display: none; position: fixed; top: 50%; left: 50%;
            transform: translate(-50%,-50%);
            background: linear-gradient(180deg, rgba(15,15,35,0.95) 0%, rgba(10,10,25,0.9) 100%);
            padding: 25px 50px; font-size: 28px; border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }
    </style>
</head>
<body>
    <video id="html5video" autoplay playsinline style="position:fixed;top:120px;left:730px;width:1120px;height:630px;z-index:2;border-radius:18px;display:none;"></video>
    <div id="preview">Vista previa</div>
    <div id="preview-cap"></div>
    <div id="content" style="position:relative;z-index:10;"><div class="panel" style="text-align:center;padding:60px 40px;"><div class="logo">Quattre<span>TV</span></div><div style="color:#666;margin-top:20px;">Cargando canales...</div></div></div>
    <div id="osd" style="position:relative;z-index:10;"></div>
    <div id="vol" style="z-index:20;"></div>
    <div id="toast"></div>
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
    next_programs = {}
    for p in Program.objects.filter(
        channel__in=channels, start_time__gt=now
    ).order_by('channel_id', 'start_time'):
        next_programs.setdefault(p.channel_id, p)

    favorites = set()
    if device:
        from apps.channels.models import Favorite
        favorites = set(
            Favorite.objects.filter(user=device.user).values_list('channel_id', flat=True)
        )

    data = []
    for ch in channels:
        current = current_programs.get(ch.id)
        upcoming = next_programs.get(ch.id)
        # Only advertise archive when a recorder can actually serve it: it needs
        # catchup enabled and a multicast source being archived.
        has_archive = bool(ch.has_catchup and ch.multicast_url)
        data.append({
            'id': str(ch.id),
            'name': ch.name,
            'number': ch.number,
            'cmd': ch.stream_url,
            'logo': ch.logo_display_url,
            'censored': ch.is_adult,
            'hd': 1 if ch.is_hd else 0,
            'fav': 1 if ch.id in favorites else 0,
            'archive': 1 if has_archive else 0,
            'archive_range': ch.timeshift_hours if has_archive else 0,
            'cur_playing': current.title if current else '',
            'epg_start': current.start_time.isoformat() if current else '',
            'epg_end': current.end_time.isoformat() if current else '',
            'epg_progress': current.progress_percent if current else 0,
            'epg_next': upcoming.title if upcoming else '',
            'epg_next_start': timezone.localtime(upcoming.start_time).strftime('%H:%M') if upcoming else '',
            'epg_cur_start': timezone.localtime(current.start_time).strftime('%H:%M') if current else '',
            'epg_cur_end': timezone.localtime(current.end_time).strftime('%H:%M') if current else '',
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
