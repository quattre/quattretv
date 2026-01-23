import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/models/program.dart';
import '../../../core/constants/api_constants.dart';

// Current program for a channel
final currentProgramProvider = FutureProvider.family<Program?, int>((ref, channelId) async {
  final dio = ref.read(dioProvider);

  try {
    final response = await dio.get(
      ApiConstants.epgNow,
      queryParameters: {'channel': channelId},
    );

    final List<dynamic> data = response.data;
    if (data.isEmpty) return null;

    return Program.fromJson(data.first);
  } catch (e) {
    return null;
  }
});

// Schedule for a channel
final channelScheduleProvider = FutureProvider.family<List<Program>, int>((ref, channelId) async {
  final dio = ref.read(dioProvider);

  final response = await dio.get(
    ApiConstants.epgSchedule,
    queryParameters: {
      'channel': channelId,
      'hours': 24,
    },
  );

  final List<dynamic> data = response.data;
  return data.map((json) => Program.fromJson(json)).toList();
});

// EPG Grid
final epgGridProvider = FutureProvider.family<List<EpgGridChannel>, List<int>>((ref, channelIds) async {
  final dio = ref.read(dioProvider);

  final response = await dio.get(
    ApiConstants.epgGrid,
    queryParameters: {
      'channels': channelIds,
      'hours': 6,
    },
  );

  final List<dynamic> data = response.data;
  return data.map((json) => EpgGridChannel.fromJson(json)).toList();
});

// Selected date for EPG
final epgSelectedDateProvider = StateProvider<DateTime>((ref) {
  return DateTime.now();
});

class EpgGridChannel {
  final int channelId;
  final String channelName;
  final int channelNumber;
  final List<Program> programs;

  EpgGridChannel({
    required this.channelId,
    required this.channelName,
    required this.channelNumber,
    required this.programs,
  });

  factory EpgGridChannel.fromJson(Map<String, dynamic> json) {
    return EpgGridChannel(
      channelId: json['channel_id'],
      channelName: json['channel_name'],
      channelNumber: json['channel_number'],
      programs: (json['programs'] as List)
          .map((p) => Program.fromJson(p))
          .toList(),
    );
  }
}
