import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/api/models/program.dart';
import '../../../core/widgets/loading_widget.dart';
import '../../channels/providers/channels_provider.dart';
import '../providers/epg_provider.dart';

class EpgScreen extends ConsumerStatefulWidget {
  const EpgScreen({super.key});

  @override
  ConsumerState<EpgScreen> createState() => _EpgScreenState();
}

class _EpgScreenState extends ConsumerState<EpgScreen> {
  final ScrollController _horizontalController = ScrollController();
  final ScrollController _verticalController = ScrollController();
  int? _selectedChannelId;

  @override
  void dispose() {
    _horizontalController.dispose();
    _verticalController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final channelsAsync = ref.watch(channelsProvider);
    final selectedDate = ref.watch(epgSelectedDateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Guía de Programación'),
        actions: [
          // Date selector
          TextButton.icon(
            onPressed: () => _selectDate(context),
            icon: const Icon(Icons.calendar_today, size: 18),
            label: Text(
              DateFormat('EEE d MMM', 'es').format(selectedDate),
              style: const TextStyle(color: AppColors.textPrimary),
            ),
          ),
        ],
      ),
      body: channelsAsync.when(
        data: (channels) {
          if (channels.isEmpty) {
            return const Center(
              child: Text('No hay canales disponibles'),
            );
          }

          return Row(
            children: [
              // Channel list (left side)
              SizedBox(
                width: 150,
                child: ListView.builder(
                  controller: _verticalController,
                  itemCount: channels.length,
                  itemBuilder: (context, index) {
                    final channel = channels[index];
                    final isSelected = _selectedChannelId == channel.id;

                    return InkWell(
                      onTap: () {
                        setState(() => _selectedChannelId = channel.id);
                      },
                      child: Container(
                        height: 70,
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        decoration: BoxDecoration(
                          color: isSelected
                              ? AppColors.primary.withOpacity(0.2)
                              : null,
                          border: Border(
                            bottom: BorderSide(
                              color: AppColors.surface,
                              width: 1,
                            ),
                          ),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: AppColors.surface,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                '${channel.number}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                channel.name,
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),

              // EPG grid (right side)
              Expanded(
                child: _selectedChannelId != null
                    ? _buildChannelSchedule(_selectedChannelId!)
                    : const Center(
                        child: Text(
                          'Selecciona un canal',
                          style: TextStyle(color: AppColors.textMuted),
                        ),
                      ),
              ),
            ],
          );
        },
        loading: () => const LoadingWidget(),
        error: (error, _) => Center(child: Text('Error: $error')),
      ),
    );
  }

  Widget _buildChannelSchedule(int channelId) {
    final scheduleAsync = ref.watch(channelScheduleProvider(channelId));

    return scheduleAsync.when(
      data: (programs) {
        if (programs.isEmpty) {
          return const Center(
            child: Text(
              'No hay programación disponible',
              style: TextStyle(color: AppColors.textMuted),
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.all(8),
          itemCount: programs.length,
          itemBuilder: (context, index) {
            final program = programs[index];
            return _ProgramCard(program: program);
          },
        );
      },
      loading: () => const LoadingWidget(),
      error: (error, _) => Center(child: Text('Error: $error')),
    );
  }

  Future<void> _selectDate(BuildContext context) async {
    final currentDate = ref.read(epgSelectedDateProvider);

    final selectedDate = await showDatePicker(
      context: context,
      initialDate: currentDate,
      firstDate: DateTime.now().subtract(const Duration(days: 7)),
      lastDate: DateTime.now().add(const Duration(days: 7)),
    );

    if (selectedDate != null) {
      ref.read(epgSelectedDateProvider.notifier).state = selectedDate;
    }
  }
}

class _ProgramCard extends StatelessWidget {
  final Program program;

  const _ProgramCard({required this.program});

  @override
  Widget build(BuildContext context) {
    final timeFormat = DateFormat('HH:mm');
    final isCurrent = program.isCurrent;

    return Card(
      color: isCurrent ? AppColors.primary.withOpacity(0.15) : null,
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () {
          if (isCurrent) {
            context.push('/player/${program.channelId}');
          } else if (program.startTime.isBefore(DateTime.now())) {
            // Catchup
            context.push(
              '/player/${program.channelId}?startTime=${program.startTime.toIso8601String()}',
            );
          }
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Time
              SizedBox(
                width: 80,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      timeFormat.format(program.startTime),
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: isCurrent ? AppColors.primary : null,
                      ),
                    ),
                    Text(
                      timeFormat.format(program.endTime),
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ),

              // Progress indicator for current program
              if (isCurrent)
                Container(
                  width: 4,
                  height: 40,
                  margin: const EdgeInsets.only(right: 12),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),

              // Program info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      program.title,
                      style: const TextStyle(
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (program.description != null &&
                        program.description!.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        program.description!,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textSecondary,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        if (program.category != null) ...[
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.surface,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              program.category!,
                              style: const TextStyle(
                                fontSize: 10,
                                color: AppColors.textMuted,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                        ],
                        Text(
                          '${program.durationMinutes} min',
                          style: const TextStyle(
                            fontSize: 10,
                            color: AppColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // Actions
              if (isCurrent)
                const Icon(
                  Icons.play_circle_fill,
                  color: AppColors.primary,
                )
              else if (program.startTime.isBefore(DateTime.now()))
                const Icon(
                  Icons.replay,
                  color: AppColors.textMuted,
                  size: 20,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
