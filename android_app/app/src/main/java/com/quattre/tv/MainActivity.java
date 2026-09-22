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
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

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

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);

        // Una television no se apaga sola mientras hay un canal puesto.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#080b0d"));
        setContentView(web);

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

        web.loadUrl(CARGADOR);
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
        web.loadUrl("about:blank");
    }

    @Override
    protected void onDestroy() {
        web.destroy();
        super.onDestroy();
    }
}
