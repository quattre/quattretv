import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../../core/api/models/channel.dart';
import '../../../core/api/models/program.dart';
import '../../../core/config/app_theme.dart';

class PlayerControls extends StatelessWidget {
  final VideoPlayerController? controller;
  final Channel? channel;
  final Program? currentProgram;
  final VoidCallback onBack;
  final VoidCallback onPlayPause;
  final VoidCallback onPreviousChannel;
  final VoidCallback onNextChannel;

  const PlayerControls({
    super.key,
    this.controller,
    this.channel,
    this.currentProgram,
    required this.onBack,
    required this.onPlayPause,
    required this.onPreviousChannel,
    required this.onNextChannel,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.black.withOpacity(0.7),
            Colors.transparent,
            Colors.transparent,
            Colors.black.withOpacity(0.7),
          ],
          stops: const [0, 0.3, 0.7, 1],
        ),
      ),
      child: SafeArea(
        child: Column(
          children: [
            // Top bar
            _buildTopBar(context),

            const Spacer(),

            // Center controls
            _buildCenterControls(),

            const Spacer(),

            // Bottom bar
            _buildBottomBar(context),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          // Back button
          IconButton(
            onPressed: onBack,
            icon: const Icon(Icons.arrow_back, color: Colors.white),
          ),
          const SizedBox(width: 8),

          // Channel info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    if (channel != null) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.primary,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '${channel!.number}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                    ],
                    Expanded(
                      child: Text(
                        channel?.name ?? 'Canal',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                if (currentProgram != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    currentProgram!.title,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),

          // Live indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.live,
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.circle, size: 8, color: Colors.white),
                SizedBox(width: 4),
                Text(
                  'EN VIVO',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 12,
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

  Widget _buildCenterControls() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Previous channel
        IconButton(
          onPressed: onPreviousChannel,
          icon: const Icon(
            Icons.skip_previous,
            color: Colors.white,
            size: 48,
          ),
        ),
        const SizedBox(width: 24),

        // Play/Pause
        Container(
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.2),
            shape: BoxShape.circle,
          ),
          child: IconButton(
            onPressed: onPlayPause,
            iconSize: 64,
            icon: Icon(
              controller?.value.isPlaying == true
                  ? Icons.pause
                  : Icons.play_arrow,
              color: Colors.white,
            ),
          ),
        ),
        const SizedBox(width: 24),

        // Next channel
        IconButton(
          onPressed: onNextChannel,
          icon: const Icon(
            Icons.skip_next,
            color: Colors.white,
            size: 48,
          ),
        ),
      ],
    );
  }

  Widget _buildBottomBar(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Program progress
          if (currentProgram != null) ...[
            Row(
              children: [
                Text(
                  _formatTime(currentProgram!.startTime),
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: LinearProgressIndicator(
                      value: currentProgram!.progressPercent / 100,
                      backgroundColor: Colors.white24,
                      valueColor: const AlwaysStoppedAnimation(AppColors.primary),
                    ),
                  ),
                ),
                Text(
                  _formatTime(currentProgram!.endTime),
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 12),
          ],

          // Action buttons
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _ActionButton(
                icon: Icons.favorite_border,
                label: 'Favorito',
                onTap: () {},
              ),
              if (channel?.hasTimeshift == true)
                _ActionButton(
                  icon: Icons.history,
                  label: 'Timeshift',
                  onTap: () {},
                ),
              if (channel?.hasCatchup == true)
                _ActionButton(
                  icon: Icons.replay,
                  label: 'Catchup',
                  onTap: () {},
                ),
              _ActionButton(
                icon: Icons.fiber_manual_record,
                label: 'Grabar',
                onTap: () {},
              ),
              _ActionButton(
                icon: Icons.info_outline,
                label: 'Info',
                onTap: () {},
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatTime(DateTime time) {
    return '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: Colors.white, size: 24),
            const SizedBox(height: 4),
            Text(
              label,
              style: const TextStyle(color: Colors.white70, fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }
}
