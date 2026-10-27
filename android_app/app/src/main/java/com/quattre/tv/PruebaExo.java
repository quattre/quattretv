package com.quattre.tv;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;

import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.Format;
import androidx.media3.common.TrackGroup;
import androidx.media3.common.Tracks;
import androidx.media3.common.VideoSize;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.hls.HlsMediaSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.ui.PlayerView;

/**
 * PRUEBA: ExoPlayer con un canal. Los canales de TDT no emiten IDR, solo
 * I-frames con punto de recuperacion, y ni Chromium (MSE) ni el MediaPlayer
 * del sistema arrancan con ellos. ExoPlayer los admite en HLS por defecto
 * (FLAG_ALLOW_NON_IDR_KEYFRAMES). Se lanza con:
 *   am start -n com.quattre.tv/.PruebaExo -e url https://.../index.m3u8
 */
public class PruebaExo extends Activity {
    private ExoPlayer player;

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        String url = getIntent().getStringExtra("url");
        Log.i("QuattreTV", "EXO abriendo " + url);

        PlayerView vista = new PlayerView(this);
        vista.setUseController(false);
        setContentView(vista);

        player = new ExoPlayer.Builder(this).build();
        vista.setPlayer(player);
        player.addListener(new Player.Listener() {
            @Override public void onVideoSizeChanged(VideoSize s) {
                Log.i("QuattreTV", "EXO video " + s.width + "x" + s.height);
            }
            @Override public void onPlaybackStateChanged(int st) {
                Log.i("QuattreTV", "EXO estado " + st + " (3=listo) pos=" + player.getCurrentPosition());
            }
            @Override public void onRenderedFirstFrame() {
                Log.i("QuattreTV", "EXO PRIMER FOTOGRAMA PINTADO");
            }
            // Que pistas ha encontrado ExoPlayer dentro del MPEG-TS, sin
            // tocar nada en el CDN: es la pregunta de la accesibilidad.
            @Override public void onTracksChanged(Tracks pistas) {
                Log.i("QuattreTV", "EXO PISTAS: " + pistas.getGroups().size() + " grupos");
                for (Tracks.Group g : pistas.getGroups()) {
                    TrackGroup tg = g.getMediaTrackGroup();
                    for (int i = 0; i < tg.length; i++) {
                        Format f = tg.getFormat(i);
                        Log.i("QuattreTV", String.format(
                            "EXO   mime=%s codecs=%s id=%s idioma=%s canales=%d roles=%d sel_flags=%d canal_acc=%d sel=%s admitida=%s",
                            f.sampleMimeType, f.codecs, f.id, f.language, f.channelCount,
                            f.roleFlags, f.selectionFlags, f.accessibilityChannel,
                            g.isTrackSelected(i), g.isTrackSupported(i)));
                    }
                }
            }
            @Override public void onPlayerError(PlaybackException e) {
                Log.i("QuattreTV", "EXO ERROR " + e.getErrorCodeName() + ": " + e.getMessage());
            }
        });
        // Una lista .m3u8 va por HLS; un .ts suelto, por el camino normal. Asi
        // se puede comparar el mismo contenido con y sin la capa de HLS.
        if (url != null && url.contains(".m3u8")) {
            player.setMediaSource(new HlsMediaSource.Factory(new DefaultHttpDataSource.Factory())
                    .createMediaSource(MediaItem.fromUri(url)));
        } else {
            player.setMediaItem(MediaItem.fromUri(url));
        }
        player.setPlayWhenReady(true);
        player.prepare();
    }

    private static String tipo(String mime) {
        if (mime == null) return "?";
        if (mime.startsWith("video")) return "VIDEO";
        if (mime.startsWith("audio")) return "AUDIO";
        if (mime.startsWith("text") || mime.startsWith("application")) return "SUBTITULO";
        return mime;
    }

    @Override
    protected void onDestroy() {
        if (player != null) player.release();
        super.onDestroy();
    }
}
