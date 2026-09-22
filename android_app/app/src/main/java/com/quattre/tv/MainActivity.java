package com.quattre.tv;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.widget.FrameLayout;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.VideoSize;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.hls.HlsMediaSource;
import androidx.media3.ui.AspectRatioFrameLayout;
import androidx.media3.ui.PlayerView;
import androidx.webkit.WebViewAssetLoader;

/**
 * La app de Android TV es un envoltorio fino, igual que la de LG y la de
 * Samsung: una sola pantalla con un WebView que carga el cargador del paquete
 * (el MISMO index.html de lg_app, copiado por empaquetar.sh) y este salta al
 * portal que vive en nuestros servidores. Todo lo que se arregle en el portal
 * llega aqui sin volver a pasar por Google Play.
 *
 * Lo unico que tiene que hacer esta clase es lo que una pagina web no puede
 * hacer sola en Android:
 *   - servir el cargador con un origen https (WebViewAssetLoader),
 *   - traducir las teclas del mando que Chromium no pasa a la pagina,
 *   - y salir de la app con el boton atras en la pantalla principal.
 */
public class MainActivity extends Activity {

    private static final String TAG = "QuattreTV";

    // El cargador va dentro del paquete, pero se sirve desde este origen https
    // ficticio (lo resuelve WebViewAssetLoader, no sale nada a la red). Asi el
    // XMLHttpRequest a /ping es una peticion entre origenes normal, que el
    // servidor ya permite (Access-Control-Allow-Origin: *), y no hay que abrir
    // el acceso universal desde file://, que Google Play señala como riesgo.
    private static final String ORIGEN_PAQUETE = "https://appassets.androidplatform.net";
    private static final String CARGADOR = ORIGEN_PAQUETE + "/assets/index.html";

    // Marca en el user-agent para que el portal sepa que esta en un televisor
    // (usa el reproductor nativo en vez de hls.js) y el middleware, que el
    // aparato es de tipo android.
    private static final String MARCA_UA = " QuattreTV-AndroidTV/" + BuildConfig.VERSION_NAME;

    private WebView web;
    private WebViewAssetLoader recursos;
    private boolean estuvoParada = false;

    // El video NO lo pinta el WebView. Los canales de TDT no emiten ningun
    // IDR (solo I-frames con punto de recuperacion) y Chromium no arranca sin
    // IDR; ExoPlayer si. Asi que el video va en un ExoPlayer POR DETRAS del
    // WebView, que es transparente, y el portal le dice por el puente
    // QuattreAndroid que reproducir y donde colocarlo -- igual que hace con el
    // plano de video del deco o del televisor. La interfaz sigue siendo la
    // pagina: cambiarla no obliga a actualizar la app.
    private FrameLayout raiz;
    private PlayerView vista;
    private ExoPlayer player;
    private String urlActual = null;
    private float volumen = 1f;
    private final float[] hueco = {0f, 0f, 1f, 1f};   // x, y, ancho, alto en fracciones

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);

        // Una television no se apaga sola mientras hay un canal puesto.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);

        raiz = new FrameLayout(this);
        raiz.setBackgroundColor(Color.parseColor("#080b0d"));

        vista = new PlayerView(this);
        vista.setUseController(false);
        vista.setResizeMode(AspectRatioFrameLayout.RESIZE_MODE_FIT);
        vista.setVisibility(View.INVISIBLE);
        raiz.addView(vista, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        web = new WebView(this);
        // Transparente: el video esta debajo y solo asoma donde la pagina no pinta.
        web.setBackgroundColor(Color.TRANSPARENT);
        raiz.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(raiz);
        // Si cambia el tamaño de la ventana, el hueco del video se recalcula.
        raiz.addOnLayoutChangeListener((v, l, tp, r, b, ol, ot, or, ob) -> {
            if (r - l != or - ol || b - tp != ob - ot) colocarVista();
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        // localStorage: ahi guarda el cargador el identificador del aparato y
        // el ultimo servidor que contesto. Sin esto cada arranque seria un
        // equipo nuevo.
        s.setDomStorageEnabled(true);
        // El portal arranca el video solo, sin que nadie pulse nada.
        s.setMediaPlaybackRequiresUserGesture(false);
        // El portal y el cargador llevan <meta viewport width=1920>: se
        // maquetan a 1920x1080 y se encajan en la pantalla que haya, como en LG.
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        // ...pero el modo "overview" no reduce la pagina por si solo en una
        // pantalla de densidad 2 (el emulador de TV, muchos televisores): se
        // veia al doble, con la lista tapando el video. Se fija la escala a
        // mano: la rejilla de 1920 del portal = el ancho real de la pantalla.
        // Asi las fracciones que manda colocar() coinciden con la pagina.
        int anchoPantalla = getResources().getDisplayMetrics().widthPixels;
        web.setInitialScale(Math.round(100f * anchoPantalla / 1920f));
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setUserAgentString(s.getUserAgentString() + MARCA_UA);

        recursos = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                return recursos.shouldInterceptRequest(r.getUrl());
            }

            // Solo se navega a lo nuestro. Un enlace a cualquier otro sitio se
            // ignora: la app no es un navegador.
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                String host = u.getHost() == null ? "" : u.getHost().toLowerCase();
                boolean nuestro = host.equals("appassets.androidplatform.net")
                        || host.equals("quattre.com") || host.endsWith(".quattre.com");
                if (!nuestro) Log.w(TAG, "Navegacion bloqueada a " + u);
                return !nuestro;
            }

            // Si se cae la red a mitad, el WebView pondria su pagina de error
            // en ingles y sin salida. Mejor volver al cargador, que reintenta
            // solo y lo explica en pantalla.
            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (!r.isForMainFrame()) return;
                Log.w(TAG, "Error cargando " + r.getUrl() + ": " + e.getDescription());
                v.postDelayed(() -> v.loadUrl(CARGADOR), 3000);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            // Lo que la pagina escribe por consola sale en logcat, que es lo
            // unico que se puede leer desde fuera sin depurador.
            @Override
            public boolean onConsoleMessage(ConsoleMessage m) {
                Log.i(TAG, "js: " + m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
                return true;
            }
        });

        web.addJavascriptInterface(new Puente(), "QuattreAndroid");
        web.loadUrl(CARGADOR);
    }

    // ---- Video: ExoPlayer detras de la pagina --------------------------------

    /** Lo que la pagina puede pedirle a la app. Llega en un hilo aparte: todo al hilo de la interfaz. */
    private class Puente {
        @JavascriptInterface public void reproducir(String url) { runOnUiThread(() -> reproducir_(url)); }
        @JavascriptInterface public void parar() { runOnUiThread(() -> parar_()); }
        @JavascriptInterface public void colocar(double x, double y, double ancho, double alto) {
            runOnUiThread(() -> {
                hueco[0] = (float) x; hueco[1] = (float) y; hueco[2] = (float) ancho; hueco[3] = (float) alto;
                colocarVista();
            });
        }
        @JavascriptInterface public void volumen(int v) {
            runOnUiThread(() -> { volumen = Math.max(0, Math.min(100, v)) / 100f; if (player != null) player.setVolume(volumen); });
        }
    }

    private void crearPlayer() {
        if (player != null) return;
        player = new ExoPlayer.Builder(this).build();
        player.setVolume(volumen);
        player.addListener(new Player.Listener() {
            @Override public void onVideoSizeChanged(VideoSize s) {
                Log.i(TAG, "video " + s.width + "x" + s.height);
            }
            @Override public void onRenderedFirstFrame() {
                vista.setVisibility(View.VISIBLE);
            }
            // Un directo se cae de vez en cuando (un segmento que no llega,
            // un corte). Se vuelve a enganchar al borde del directo solo.
            @Override public void onPlayerError(PlaybackException e) {
                Log.w(TAG, "video: " + e.getErrorCodeName() + " " + e.getMessage());
                if (urlActual == null) return;
                raiz.postDelayed(() -> {
                    if (player == null || urlActual == null) return;
                    player.seekToDefaultPosition();
                    player.prepare();
                }, 3000);
            }
        });
        vista.setPlayer(player);
    }

    private void reproducir_(String url) {
        crearPlayer();
        urlActual = url;
        Log.i(TAG, "video: " + url);
        player.setMediaSource(new HlsMediaSource.Factory(new DefaultHttpDataSource.Factory())
                .createMediaSource(MediaItem.fromUri(url)));
        player.setPlayWhenReady(true);
        player.prepare();
        colocarVista();
    }

    private void parar_() {
        urlActual = null;
        if (player != null) player.stop();
        vista.setVisibility(View.INVISIBLE);
    }

    /** Coloca el video en el hueco que ha pedido la pagina (fracciones de pantalla). */
    private void colocarVista() {
        int W = raiz.getWidth(), H = raiz.getHeight();
        if (W == 0 || H == 0) return;
        FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) vista.getLayoutParams();
        lp.leftMargin = Math.round(hueco[0] * W);
        lp.topMargin = Math.round(hueco[1] * H);
        lp.width = Math.round(hueco[2] * W);
        lp.height = Math.round(hueco[3] * H);
        vista.setLayoutParams(lp);
    }

    // ---- Teclas del mando -------------------------------------------------
    //
    // Las flechas, el OK, los numeros y el teclado llegan solos a la pagina.
    // Lo que NO llega, o llega con otro numero, se traduce aqui a los codigos
    // que el portal ya entiende de LG: colores 403-406, informacion 457, atras
    // 461, canal +/- como pagina arriba/abajo, y reproducir como OK.
    @Override
    public boolean dispatchKeyEvent(KeyEvent e) {
        int codigo = e.getKeyCode();
        if (codigo == KeyEvent.KEYCODE_BACK) {
            if (e.getAction() == KeyEvent.ACTION_DOWN && e.getRepeatCount() == 0) atras();
            return true;
        }
        int traducida = traducir(codigo);
        if (traducida == 0) return super.dispatchKeyEvent(e);
        if (e.getAction() == KeyEvent.ACTION_DOWN) inyectarTecla(traducida);
        return true;
    }

    private static int traducir(int codigo) {
        switch (codigo) {
            case KeyEvent.KEYCODE_PROG_RED:    return 403;
            case KeyEvent.KEYCODE_PROG_GREEN:  return 404;
            case KeyEvent.KEYCODE_PROG_YELLOW: return 405;
            case KeyEvent.KEYCODE_PROG_BLUE:   return 406;
            case KeyEvent.KEYCODE_INFO:        return 457;
            case KeyEvent.KEYCODE_GUIDE:       return 457;
            case KeyEvent.KEYCODE_CHANNEL_UP:  return 33;
            case KeyEvent.KEYCODE_CHANNEL_DOWN:return 34;
            case KeyEvent.KEYCODE_MEDIA_PLAY:
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE: return 415;
            default: return 0;
        }
    }

    // Dispara un keydown en la pagina con el codigo dado. El portal lee
    // e.keyCode, que en un KeyboardEvent construido a mano sale siempre 0, asi
    // que se define a mano sobre el evento.
    private void inyectarTecla(int codigo) {
        web.evaluateJavascript(
                "(function(k){var t=document.activeElement||document.body||document;"
                + "var e=document.createEvent('Event');e.initEvent('keydown',true,true);"
                + "Object.defineProperty(e,'keyCode',{get:function(){return k}});"
                + "Object.defineProperty(e,'which',{get:function(){return k}});"
                + "t.dispatchEvent(e);})(" + codigo + ")", null);
    }

    // Atras: en Android TV lo esperado es que en la pantalla principal cierre
    // la app (en LG y Samsung eso lo hace el boton de inicio). En el resto de
    // pantallas se le pasa al portal como el 461 de LG y hace lo de siempre.
    // Si la pagina no es el portal (el cargador, el acceso), se sale.
    private void atras() {
        web.evaluateJavascript(
                "(typeof enRaiz === 'function') ? String(enRaiz()) : 'fuera'",
                valor -> {
                    Log.i(TAG, "atras: enRaiz=" + valor);
                    if (valor == null || valor.contains("fuera") || valor.contains("true")) {
                        finish();
                    } else {
                        inyectarTecla(461);
                    }
                });
    }

    // ---- Ciclo de vida ----------------------------------------------------
    //
    // Al irse a otra app (boton de inicio) se para el video; al volver, se
    // vuelve a empezar por el cargador, que es rapido y deja el reproductor
    // limpio. Un MediaPlayer que se quedo a medias no siempre se recupera.
    @Override
    protected void onPause() {
        super.onPause();
        web.onPause();
        web.pauseTimers();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.resumeTimers();
        web.onResume();
        if (estuvoParada) {
            estuvoParada = false;
            web.loadUrl(CARGADOR);
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        estuvoParada = true;
        parar_();
        web.loadUrl("about:blank");
    }

    @Override
    protected void onDestroy() {
        if (player != null) { player.release(); player = null; }
        web.destroy();
        super.onDestroy();
    }
}
