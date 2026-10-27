package com.quattre.tv;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;

import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
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
            @Override public void onPlayerError(PlaybackException e) {
                Log.i("QuattreTV", "EXO ERROR " + e.getErrorCodeName() + ": " + e.getMessage());
            }
        });
        HlsMediaSource fuente = new HlsMediaSource.Factory(new DefaultHttpDataSource.Factory())
                .createMediaSource(MediaItem.fromUri(url));
        player.setMediaSource(fuente);
        player.setPlayWhenReady(true);
        player.prepare();
    }

    @Override
    protected void onDestroy() {
        if (player != null) player.release();
        super.onDestroy();
    }
}
