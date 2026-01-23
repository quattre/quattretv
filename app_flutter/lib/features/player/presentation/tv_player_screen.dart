import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/api/models/channel.dart';
import '../../../core/api/models/program.dart';
import '../../../core/widgets/tv_focusable.dart';
import '../../channels/providers/channels_provider.dart';
import '../../epg/providers/epg_provider.dart';

/// TV-optimized video player with D-pad controls
class TvPlayerScreen extends ConsumerStatefulWidget {
  final int channelId;
  final DateTime? startTime;

  const TvPlayerScreen({
    super.key,
    required this.channelId,
    this.startTime,
  });

  @override
  ConsumerState<TvPlayerScreen> createState() => _TvPlayerScreenState();
}

class _TvPlayerScreenState extends ConsumerState<TvPlayerScreen> {
  VideoPlayerController? _controller;
  bool _isInitialized = false;
  bool _isError = false;
  String? _errorMessage;
  bool _showOverlay = true;
  bool _showChannelInfo = true;

  final FocusNode _playerFocusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _enterFullscreen();
    WakelockPlus.enable();
    _initPlayer();
    _hideOverlayAfterDelay();
  }

  Future<void> _enterFullscreen() async {
    await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    await SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
  }

  Future<void> _exitFullscreen() async {
    await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    await SystemChrome.setPreferredOrientations(DeviceOrientation.values);
  }

  void _hideOverlayAfterDelay() {
    Future.delayed(const Duration(seconds: 5), () {
      if (mounted && _showOverlay) {
        setState(() {
          _showOverlay = false;
          _showChannelInfo = false;
        });
      }
    });
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

      _controller = VideoPlayerController.networkUrl(Uri.parse(url));
      await _controller!.initialize();
      await _controller!.play();

      setState(() => _isInitialized = true);
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
    _controller?.dispose();
    _playerFocusNode.dispose();
    WakelockPlus.disable();
    _exitFullscreen();
    super.dispose();
  }

  KeyEventResult _handleKeyEvent(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent) return KeyEventResult.ignored;

    // Show overlay on any key press
    if (!_showOverlay) {
      setState(() {
        _showOverlay = true;
        _showChannelInfo = true;
      });
      _hideOverlayAfterDelay();
      return KeyEventResult.handled;
    }

    // Handle D-pad navigation
    switch (event.logicalKey) {
      case LogicalKeyboardKey.arrowUp:
        _changeChannel(1);
        return KeyEventResult.handled;

      case LogicalKeyboardKey.arrowDown:
        _changeChannel(-1);
        return KeyEventResult.handled;

      case LogicalKeyboardKey.arrowLeft:
        _seekBackward();
        return KeyEventResult.handled;

      case LogicalKeyboardKey.arrowRight:
        _seekForward();
        return KeyEventResult.handled;

      case LogicalKeyboardKey.select:
      case LogicalKeyboardKey.enter:
        _togglePlayPause();
        return KeyEventResult.handled;

      case LogicalKeyboardKey.goBack:
      case LogicalKeyboardKey.escape:
        Navigator.of(context).pop();
        return KeyEventResult.handled;

      case LogicalKeyboardKey.mediaPlayPause:
        _togglePlayPause();
        return KeyEventResult.handled;

      case LogicalKeyboardKey.mediaStop:
        Navigator.of(context).pop();
        return KeyEventResult.handled;
    }

    return KeyEventResult.ignored;
  }

  void _togglePlayPause() {
    if (_controller == null) return;
    if (_controller!.value.isPlaying) {
      _controller!.pause();
    } else {
      _controller!.play();
    }
    setState(() {});
  }

  void _seekForward() {
    if (_controller == null) return;
    final position = _controller!.value.position;
    _controller!.seekTo(position + const Duration(seconds: 30));
  }

  void _seekBackward() {
    if (_controller == null) return;
    final position = _controller!.value.position;
    _controller!.seekTo(position - const Duration(seconds: 10));
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
          builder: (_) => TvPlayerScreen(channelId: newChannel.id),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final channelAsync = ref.watch(channelProvider(widget.channelId));
    final programAsync = ref.watch(currentProgramProvider(widget.channelId));

    return Scaffold(
      backgroundColor: Colors.black,
      body: Focus(
        focusNode: _playerFocusNode,
        autofocus: true,
        onKeyEvent: _handleKeyEvent,
        child: GestureDetector(
          onTap: () {
            setState(() {
              _showOverlay = !_showOverlay;
              _showChannelInfo = _showOverlay;
            });
            if (_showOverlay) _hideOverlayAfterDelay();
          },
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
                _buildError()
              else
                _buildLoading(),

              // Channel info overlay (top)
              AnimatedPositioned(
                duration: const Duration(milliseconds: 300),
                top: _showChannelInfo ? 0 : -200,
                left: 0,
                right: 0,
                child: _buildChannelInfo(
                  channelAsync.valueOrNull,
                  programAsync.valueOrNull,
                ),
              ),

              // Controls overlay (bottom)
              AnimatedPositioned(
                duration: const Duration(milliseconds: 300),
                bottom: _showOverlay ? 0 : -150,
                left: 0,
                right: 0,
                child: _buildControls(),
              ),

              // Center play/pause indicator
              if (_showOverlay && _isInitialized)
                Center(
                  child: Container(
                    width: 100,
                    height: 100,
                    decoration: BoxDecoration(
                      color: Colors.black38,
                      borderRadius: BorderRadius.circular(50),
                    ),
                    child: Icon(
                      _controller!.value.isPlaying
                          ? Icons.pause
                          : Icons.play_arrow,
                      size: 60,
                      color: Colors.white,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLoading() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(color: AppColors.primary),
          SizedBox(height: 24),
          Text(
            'Cargando canal...',
            style: TextStyle(color: Colors.white70, fontSize: 18),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 80, color: AppColors.error),
          const SizedBox(height: 24),
          const Text(
            'Error al reproducir',
            style: TextStyle(color: Colors.white, fontSize: 24),
          ),
          const SizedBox(height: 8),
          Text(
            _errorMessage ?? '',
            style: const TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 32),
          TvFocusable(
            autofocus: true,
            onSelect: () {
              setState(() {
                _isError = false;
                _isInitialized = false;
              });
              _initPlayer();
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Reintentar',
                style: TextStyle(color: Colors.white, fontSize: 18),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChannelInfo(Channel? channel, Program? program) {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.black.withOpacity(0.8),
            Colors.transparent,
          ],
        ),
      ),
      child: Row(
        children: [
          // Channel info
          if (channel != null) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${channel.number}',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 20),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    channel.name,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (program != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      program.title,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 18,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],

          // Live indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.live,
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Row(
              children: [
                Icon(Icons.circle, size: 12, color: Colors.white),
                SizedBox(width: 8),
                Text(
                  'EN VIVO',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControls() {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.bottomCenter,
          end: Alignment.topCenter,
          colors: [
            Colors.black.withOpacity(0.8),
            Colors.transparent,
          ],
        ),
      ),
      child: Column(
        children: [
          // Progress bar (for timeshift)
          if (widget.startTime != null && _controller != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: LinearProgressIndicator(
                value: _controller!.value.position.inSeconds /
                    (_controller!.value.duration.inSeconds + 1),
                backgroundColor: Colors.white24,
                valueColor: const AlwaysStoppedAnimation(AppColors.primary),
              ),
            ),

          // Control hints
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _ControlHint(icon: Icons.arrow_upward, label: 'Canal +'),
              _ControlHint(icon: Icons.arrow_downward, label: 'Canal -'),
              _ControlHint(icon: Icons.arrow_back, label: '-10s'),
              _ControlHint(icon: Icons.arrow_forward, label: '+30s'),
              _ControlHint(icon: Icons.radio_button_checked, label: 'Play/Pause'),
              _ControlHint(icon: Icons.arrow_back_ios, label: 'Volver'),
            ],
          ),
        ],
      ),
    );
  }
}

class _ControlHint extends StatelessWidget {
  final IconData icon;
  final String label;

  const _ControlHint({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white54, size: 24),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(color: Colors.white54, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
