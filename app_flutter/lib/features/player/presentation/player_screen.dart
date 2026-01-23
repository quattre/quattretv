import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/api/models/channel.dart';
import '../../../core/api/models/program.dart';
import '../../channels/providers/channels_provider.dart';
import '../../epg/providers/epg_provider.dart';
import 'player_controls.dart';

class PlayerScreen extends ConsumerStatefulWidget {
  final int channelId;
  final DateTime? startTime; // For timeshift/catchup

  const PlayerScreen({
    super.key,
    required this.channelId,
    this.startTime,
  });

  @override
  ConsumerState<PlayerScreen> createState() => _PlayerScreenState();
}

class _PlayerScreenState extends ConsumerState<PlayerScreen> {
  VideoPlayerController? _controller;
  bool _isInitialized = false;
  bool _isError = false;
  String? _errorMessage;
  bool _showControls = true;
  bool _isFullscreen = false;

  @override
  void initState() {
    super.initState();
    _setLandscape();
    WakelockPlus.enable();
    _initPlayer();
  }

  Future<void> _setLandscape() async {
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  Future<void> _resetOrientation() async {
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  }

  Future<void> _initPlayer() async {
    try {
      final streamUrl = await ref.read(
        channelStreamUrlProvider(widget.channelId).future,
      );

      String url = streamUrl;
      if (widget.startTime != null) {
        final timestamp = widget.startTime!.millisecondsSinceEpoch ~/ 1000;
        url += '?utc=$timestamp';
      }

      _controller = VideoPlayerController.networkUrl(
        Uri.parse(url),
        videoPlayerOptions: VideoPlayerOptions(
          mixWithOthers: false,
          allowBackgroundPlayback: false,
        ),
      );

      await _controller!.initialize();
      await _controller!.play();

      setState(() {
        _isInitialized = true;
      });

      _controller!.addListener(_videoListener);
    } catch (e) {
      setState(() {
        _isError = true;
        _errorMessage = e.toString();
      });
    }
  }

  void _videoListener() {
    if (_controller!.value.hasError) {
      setState(() {
        _isError = true;
        _errorMessage = _controller!.value.errorDescription;
      });
    }
  }

  @override
  void dispose() {
    _controller?.removeListener(_videoListener);
    _controller?.dispose();
    WakelockPlus.disable();
    _resetOrientation();
    super.dispose();
  }

  void _toggleControls() {
    setState(() {
      _showControls = !_showControls;
    });

    if (_showControls) {
      Future.delayed(const Duration(seconds: 5), () {
        if (mounted && _showControls) {
          setState(() => _showControls = false);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final channelAsync = ref.watch(channelProvider(widget.channelId));
    final currentProgramAsync = ref.watch(currentProgramProvider(widget.channelId));

    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        onTap: _toggleControls,
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Video player
            if (_isInitialized && _controller != null)
              Center(
                child: AspectRatio(
                  aspectRatio: _controller!.value.aspectRatio,
                  child: VideoPlayer(_controller!),
                ),
              )
            else if (_isError)
              _buildErrorWidget()
            else
              _buildLoadingWidget(),

            // Controls overlay
            AnimatedOpacity(
              opacity: _showControls ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 300),
              child: IgnorePointer(
                ignoring: !_showControls,
                child: PlayerControls(
                  controller: _controller,
                  channel: channelAsync.valueOrNull,
                  currentProgram: currentProgramAsync.valueOrNull,
                  onBack: () => Navigator.of(context).pop(),
                  onPlayPause: () {
                    if (_controller!.value.isPlaying) {
                      _controller!.pause();
                    } else {
                      _controller!.play();
                    }
                    setState(() {});
                  },
                  onPreviousChannel: () => _changeChannel(-1),
                  onNextChannel: () => _changeChannel(1),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingWidget() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(color: AppColors.primary),
          SizedBox(height: 16),
          Text(
            'Cargando canal...',
            style: TextStyle(color: Colors.white70),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorWidget() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.error_outline,
            size: 64,
            color: AppColors.error,
          ),
          const SizedBox(height: 16),
          const Text(
            'Error al reproducir',
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _errorMessage ?? 'Error desconocido',
            style: const TextStyle(color: Colors.white70),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () {
              setState(() {
                _isError = false;
                _isInitialized = false;
              });
              _initPlayer();
            },
            icon: const Icon(Icons.refresh),
            label: const Text('Reintentar'),
          ),
        ],
      ),
    );
  }

  void _changeChannel(int delta) async {
    final channels = await ref.read(channelsProvider.future);
    final currentIndex = channels.indexWhere((c) => c.id == widget.channelId);

    if (currentIndex == -1) return;

    int newIndex = currentIndex + delta;
    if (newIndex < 0) newIndex = channels.length - 1;
    if (newIndex >= channels.length) newIndex = 0;

    final newChannel = channels[newIndex];

    if (mounted) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => PlayerScreen(channelId: newChannel.id),
        ),
      );
    }
  }
}
