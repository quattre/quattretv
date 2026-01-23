class Movie {
  final int id;
  final String title;
  final String? originalTitle;
  final String? description;
  final int? year;
  final int? duration;
  final double? rating;
  final String? posterUrl;
  final String? backdropUrl;
  final String? trailerUrl;
  final String? streamUrl;
  final int? categoryId;
  final String? categoryName;
  final String? genres;
  final String? director;
  final String? cast;
  final bool isHd;
  final bool is4k;
  final bool isFeatured;

  Movie({
    required this.id,
    required this.title,
    this.originalTitle,
    this.description,
    this.year,
    this.duration,
    this.rating,
    this.posterUrl,
    this.backdropUrl,
    this.trailerUrl,
    this.streamUrl,
    this.categoryId,
    this.categoryName,
    this.genres,
    this.director,
    this.cast,
    this.isHd = false,
    this.is4k = false,
    this.isFeatured = false,
  });

  factory Movie.fromJson(Map<String, dynamic> json) {
    return Movie(
      id: json['id'],
      title: json['title'],
      originalTitle: json['original_title'],
      description: json['description'],
      year: json['year'],
      duration: json['duration'],
      rating: json['rating']?.toDouble(),
      posterUrl: json['poster'] ?? json['poster_url'],
      backdropUrl: json['backdrop'] ?? json['backdrop_url'],
      trailerUrl: json['trailer_url'],
      streamUrl: json['stream_url'],
      categoryId: json['category'],
      categoryName: json['category_name'],
      genres: json['genres'],
      director: json['director'],
      cast: json['cast'],
      isHd: json['is_hd'] ?? false,
      is4k: json['is_4k'] ?? false,
      isFeatured: json['is_featured'] ?? false,
    );
  }

  String get durationFormatted {
    if (duration == null) return '';
    final hours = duration! ~/ 60;
    final minutes = duration! % 60;
    if (hours > 0) {
      return '${hours}h ${minutes}m';
    }
    return '${minutes}m';
  }

  List<String> get genreList {
    if (genres == null || genres!.isEmpty) return [];
    return genres!.split(',').map((e) => e.trim()).toList();
  }
}

class Series {
  final int id;
  final String title;
  final String? originalTitle;
  final String? description;
  final int? yearStart;
  final int? yearEnd;
  final double? rating;
  final String? posterUrl;
  final String? backdropUrl;
  final int? categoryId;
  final String? categoryName;
  final String? genres;
  final String? cast;
  final int seasonsCount;
  final bool isFeatured;
  final List<Season>? seasons;

  Series({
    required this.id,
    required this.title,
    this.originalTitle,
    this.description,
    this.yearStart,
    this.yearEnd,
    this.rating,
    this.posterUrl,
    this.backdropUrl,
    this.categoryId,
    this.categoryName,
    this.genres,
    this.cast,
    this.seasonsCount = 0,
    this.isFeatured = false,
    this.seasons,
  });

  factory Series.fromJson(Map<String, dynamic> json) {
    return Series(
      id: json['id'],
      title: json['title'],
      originalTitle: json['original_title'],
      description: json['description'],
      yearStart: json['year_start'],
      yearEnd: json['year_end'],
      rating: json['rating']?.toDouble(),
      posterUrl: json['poster'] ?? json['poster_url'],
      backdropUrl: json['backdrop'] ?? json['backdrop_url'],
      categoryId: json['category'],
      categoryName: json['category_name'],
      genres: json['genres'],
      cast: json['cast'],
      seasonsCount: json['seasons_count'] ?? 0,
      isFeatured: json['is_featured'] ?? false,
      seasons: json['seasons'] != null
          ? (json['seasons'] as List).map((e) => Season.fromJson(e)).toList()
          : null,
    );
  }

  String get yearRange {
    if (yearStart == null) return '';
    if (yearEnd == null || yearEnd == yearStart) return '$yearStart';
    return '$yearStart-$yearEnd';
  }
}

class Season {
  final int id;
  final int number;
  final String? title;
  final String? description;
  final String? posterUrl;
  final int episodesCount;
  final List<Episode>? episodes;

  Season({
    required this.id,
    required this.number,
    this.title,
    this.description,
    this.posterUrl,
    this.episodesCount = 0,
    this.episodes,
  });

  factory Season.fromJson(Map<String, dynamic> json) {
    return Season(
      id: json['id'],
      number: json['number'],
      title: json['title'],
      description: json['description'],
      posterUrl: json['poster'] ?? json['poster_url'],
      episodesCount: json['episodes_count'] ?? 0,
      episodes: json['episodes'] != null
          ? (json['episodes'] as List).map((e) => Episode.fromJson(e)).toList()
          : null,
    );
  }
}

class Episode {
  final int id;
  final int number;
  final String title;
  final String? description;
  final int? duration;
  final String? posterUrl;
  final String streamUrl;
  final DateTime? airDate;

  Episode({
    required this.id,
    required this.number,
    required this.title,
    this.description,
    this.duration,
    this.posterUrl,
    required this.streamUrl,
    this.airDate,
  });

  factory Episode.fromJson(Map<String, dynamic> json) {
    return Episode(
      id: json['id'],
      number: json['number'],
      title: json['title'],
      description: json['description'],
      duration: json['duration'],
      posterUrl: json['poster'] ?? json['poster_url'],
      streamUrl: json['stream_url'],
      airDate: json['air_date'] != null ? DateTime.parse(json['air_date']) : null,
    );
  }
}
