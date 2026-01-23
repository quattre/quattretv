enum RecordingStatus {
  scheduled,
  recording,
  completed,
  failed,
  cancelled,
}

class Recording {
  final int id;
  final int channelId;
  final String channelName;
  final int? programId;
  final String title;
  final String? description;
  final DateTime startTime;
  final DateTime endTime;
  final RecordingStatus status;
  final String? errorMessage;
  final String? streamUrl;
  final int? duration;
  final int? fileSize;

  Recording({
    required this.id,
    required this.channelId,
    required this.channelName,
    this.programId,
    required this.title,
    this.description,
    required this.startTime,
    required this.endTime,
    required this.status,
    this.errorMessage,
    this.streamUrl,
    this.duration,
    this.fileSize,
  });

  factory Recording.fromJson(Map<String, dynamic> json) {
    return Recording(
      id: json['id'],
      channelId: json['channel'],
      channelName: json['channel_name'] ?? '',
      programId: json['program'],
      title: json['title'],
      description: json['description'],
      startTime: DateTime.parse(json['start_time']),
      endTime: DateTime.parse(json['end_time']),
      status: _parseStatus(json['status']),
      errorMessage: json['error_message'],
      streamUrl: json['stream_url'],
      duration: json['duration'],
      fileSize: json['file_size'],
    );
  }

  static RecordingStatus _parseStatus(String status) {
    switch (status) {
      case 'scheduled':
        return RecordingStatus.scheduled;
      case 'recording':
        return RecordingStatus.recording;
      case 'completed':
        return RecordingStatus.completed;
      case 'failed':
        return RecordingStatus.failed;
      case 'cancelled':
        return RecordingStatus.cancelled;
      default:
        return RecordingStatus.scheduled;
    }
  }

  int get durationMinutes {
    return endTime.difference(startTime).inMinutes;
  }

  String get fileSizeFormatted {
    if (fileSize == null) return '';
    if (fileSize! < 1024) return '$fileSize B';
    if (fileSize! < 1024 * 1024) return '${(fileSize! / 1024).toStringAsFixed(1)} KB';
    if (fileSize! < 1024 * 1024 * 1024) {
      return '${(fileSize! / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(fileSize! / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
  }
}
