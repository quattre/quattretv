import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/api/api_client.dart';
import '../../../core/api/models/recording.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/widgets/loading_widget.dart';

// Recordings provider
final recordingsProvider = FutureProvider<List<Recording>>((ref) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get(ApiConstants.recordings);

  final List<dynamic> data = response.data['results'] ?? response.data;
  return data.map((json) => Recording.fromJson(json)).toList();
});

class RecordingsScreen extends ConsumerWidget {
  const RecordingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recordingsAsync = ref.watch(recordingsProvider);

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Grabaciones'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Programadas'),
              Tab(text: 'Grabando'),
              Tab(text: 'Completadas'),
            ],
            indicatorColor: AppColors.primary,
          ),
        ),
        body: recordingsAsync.when(
          data: (recordings) {
            final scheduled = recordings
                .where((r) => r.status == RecordingStatus.scheduled)
                .toList();
            final recording = recordings
                .where((r) => r.status == RecordingStatus.recording)
                .toList();
            final completed = recordings
                .where((r) => r.status == RecordingStatus.completed)
                .toList();

            return TabBarView(
              children: [
                _RecordingsList(
                  recordings: scheduled,
                  emptyMessage: 'No hay grabaciones programadas',
                ),
                _RecordingsList(
                  recordings: recording,
                  emptyMessage: 'No hay grabaciones en curso',
                ),
                _RecordingsList(
                  recordings: completed,
                  emptyMessage: 'No hay grabaciones completadas',
                ),
              ],
            );
          },
          loading: () => const LoadingWidget(),
          error: (error, _) => Center(child: Text('Error: $error')),
        ),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () {
            // TODO: Show EPG to schedule recording
          },
          icon: const Icon(Icons.add),
          label: const Text('Programar'),
          backgroundColor: AppColors.primary,
        ),
      ),
    );
  }
}

class _RecordingsList extends StatelessWidget {
  final List<Recording> recordings;
  final String emptyMessage;

  const _RecordingsList({
    required this.recordings,
    required this.emptyMessage,
  });

  @override
  Widget build(BuildContext context) {
    if (recordings.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.video_library_outlined,
              size: 64,
              color: AppColors.textMuted,
            ),
            const SizedBox(height: 16),
            Text(
              emptyMessage,
              style: const TextStyle(color: AppColors.textMuted),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(8),
      itemCount: recordings.length,
      itemBuilder: (context, index) {
        return _RecordingCard(recording: recordings[index]);
      },
    );
  }
}

class _RecordingCard extends StatelessWidget {
  final Recording recording;

  const _RecordingCard({required this.recording});

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('dd/MM/yyyy HH:mm');

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: recording.status == RecordingStatus.completed
            ? () {
                // TODO: Play recording
              }
            : null,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Status icon
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: _getStatusColor().withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  _getStatusIcon(),
                  color: _getStatusColor(),
                ),
              ),
              const SizedBox(width: 12),

              // Info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recording.title,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      recording.channelName,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(
                          Icons.access_time,
                          size: 12,
                          color: AppColors.textMuted,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          dateFormat.format(recording.startTime),
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.textMuted,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${recording.durationMinutes} min',
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.textMuted,
                          ),
                        ),
                        if (recording.fileSize != null) ...[
                          const SizedBox(width: 8),
                          Text(
                            recording.fileSizeFormatted,
                            style: const TextStyle(
                              fontSize: 11,
                              color: AppColors.textMuted,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),

              // Actions
              if (recording.status == RecordingStatus.scheduled)
                IconButton(
                  icon: const Icon(Icons.cancel_outlined),
                  onPressed: () {
                    // TODO: Cancel recording
                  },
                  color: AppColors.error,
                )
              else if (recording.status == RecordingStatus.completed)
                const Icon(
                  Icons.play_circle_fill,
                  color: AppColors.primary,
                )
              else if (recording.status == RecordingStatus.recording)
                const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.live,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getStatusColor() {
    switch (recording.status) {
      case RecordingStatus.scheduled:
        return AppColors.info;
      case RecordingStatus.recording:
        return AppColors.live;
      case RecordingStatus.completed:
        return AppColors.success;
      case RecordingStatus.failed:
        return AppColors.error;
      case RecordingStatus.cancelled:
        return AppColors.textMuted;
    }
  }

  IconData _getStatusIcon() {
    switch (recording.status) {
      case RecordingStatus.scheduled:
        return Icons.schedule;
      case RecordingStatus.recording:
        return Icons.fiber_manual_record;
      case RecordingStatus.completed:
        return Icons.check_circle;
      case RecordingStatus.failed:
        return Icons.error;
      case RecordingStatus.cancelled:
        return Icons.cancel;
    }
  }
}
