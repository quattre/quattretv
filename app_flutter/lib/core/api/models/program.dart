class Program {
  final int id;
  final int channelId;
  final String? channelName;
  final int? channelNumber;
  final String title;
  final String? description;
  final DateTime startTime;
  final DateTime endTime;
  final String? category;
  final String? posterUrl;
  final int? season;
  final int? episode;
  final bool isLive;
  final bool isNew;

  Program({
    required this.id,
    required this.channelId,
    this.channelName,
    this.channelNumber,
    required this.title,
    this.description,
    required this.startTime,
    required this.endTime,
    this.category,
    this.posterUrl,
    this.season,
    this.episode,
    this.isLive = false,
    this.isNew = false,
  });

  factory Program.fromJson(Map<String, dynamic> json) {
    return Program(
      id: json['id'],
      channelId: json['channel'],
      channelName: json['channel_name'],
      channelNumber: json['channel_number'],
      title: json['title'],
      description: json['description'],
      startTime: DateTime.parse(json['start_time']),
      endTime: DateTime.parse(json['end_time']),
      category: json['category'],
      posterUrl: json['poster'],
      season: json['season'],
      episode: json['episode'],
      isLive: json['is_live'] ?? false,
      isNew: json['is_new'] ?? false,
    );
  }

  int get durationMinutes {
    return endTime.difference(startTime).inMinutes;
  }

  bool get isCurrent {
    final now = DateTime.now();
    return startTime.isBefore(now) && endTime.isAfter(now);
  }

  double get progressPercent {
    final now = DateTime.now();
    if (now.isBefore(startTime)) return 0;
    if (now.isAfter(endTime)) return 100;

    final elapsed = now.difference(startTime).inSeconds;
    final total = endTime.difference(startTime).inSeconds;
    return (elapsed / total) * 100;
  }
}
