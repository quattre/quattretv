class Channel {
  final int id;
  final String name;
  final int number;
  final String? logoUrl;
  final int? categoryId;
  final String? categoryName;
  final bool isHd;
  final bool is4k;
  final bool isAdult;
  final bool hasEpg;
  final bool hasTimeshift;
  final bool hasCatchup;
  final String? streamUrl;
  final String? currentProgram;

  Channel({
    required this.id,
    required this.name,
    required this.number,
    this.logoUrl,
    this.categoryId,
    this.categoryName,
    this.isHd = false,
    this.is4k = false,
    this.isAdult = false,
    this.hasEpg = true,
    this.hasTimeshift = true,
    this.hasCatchup = true,
    this.streamUrl,
    this.currentProgram,
  });

  factory Channel.fromJson(Map<String, dynamic> json) {
    return Channel(
      id: json['id'],
      name: json['name'],
      number: json['number'],
      logoUrl: json['logo_display_url'] ?? json['logo_url'],
      categoryId: json['category'],
      categoryName: json['category_name'],
      isHd: json['is_hd'] ?? false,
      is4k: json['is_4k'] ?? false,
      isAdult: json['is_adult'] ?? false,
      hasEpg: json['has_epg'] ?? true,
      hasTimeshift: json['has_timeshift'] ?? true,
      hasCatchup: json['has_catchup'] ?? true,
      streamUrl: json['stream_url'],
      currentProgram: json['current_program'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'number': number,
      'logo_url': logoUrl,
      'category': categoryId,
      'category_name': categoryName,
      'is_hd': isHd,
      'is_4k': is4k,
      'is_adult': isAdult,
      'has_epg': hasEpg,
      'has_timeshift': hasTimeshift,
      'has_catchup': hasCatchup,
      'stream_url': streamUrl,
    };
  }
}

class Category {
  final int id;
  final String name;
  final String alias;
  final String? iconUrl;
  final int? parentId;
  final int channelsCount;
  final bool isAdult;

  Category({
    required this.id,
    required this.name,
    required this.alias,
    this.iconUrl,
    this.parentId,
    this.channelsCount = 0,
    this.isAdult = false,
  });

  factory Category.fromJson(Map<String, dynamic> json) {
    return Category(
      id: json['id'],
      name: json['name'],
      alias: json['alias'],
      iconUrl: json['icon'],
      parentId: json['parent'],
      channelsCount: json['channels_count'] ?? 0,
      isAdult: json['is_adult'] ?? false,
    );
  }
}
