import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/models/movie.dart';
import '../../../core/constants/api_constants.dart';

// VOD Categories
final vodCategoriesProvider = FutureProvider<List<VodCategory>>((ref) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get(ApiConstants.vodCategories);

  final List<dynamic> data = response.data['results'] ?? response.data;
  return data.map((json) => VodCategory.fromJson(json)).toList();
});

class VodCategory {
  final int id;
  final String name;
  final String alias;
  final bool isAdult;

  VodCategory({
    required this.id,
    required this.name,
    required this.alias,
    this.isAdult = false,
  });

  factory VodCategory.fromJson(Map<String, dynamic> json) {
    return VodCategory(
      id: json['id'],
      name: json['name'],
      alias: json['alias'],
      isAdult: json['is_adult'] ?? false,
    );
  }
}

// Selected VOD category
final selectedVodCategoryProvider = StateProvider<int?>((ref) => null);

// VOD type (movies/series)
enum VodType { movies, series }

final vodTypeProvider = StateProvider<VodType>((ref) => VodType.movies);

// Movies list
final moviesProvider = FutureProvider<List<Movie>>((ref) async {
  final dio = ref.read(dioProvider);
  final categoryId = ref.watch(selectedVodCategoryProvider);

  String url = ApiConstants.movies;
  if (categoryId != null) {
    url += '?category=$categoryId';
  }

  final response = await dio.get(url);

  final List<dynamic> data = response.data['results'] ?? response.data;
  return data.map((json) => Movie.fromJson(json)).toList();
});

// Series list
final seriesProvider = FutureProvider<List<Series>>((ref) async {
  final dio = ref.read(dioProvider);
  final categoryId = ref.watch(selectedVodCategoryProvider);

  String url = ApiConstants.series;
  if (categoryId != null) {
    url += '?category=$categoryId';
  }

  final response = await dio.get(url);

  final List<dynamic> data = response.data['results'] ?? response.data;
  return data.map((json) => Series.fromJson(json)).toList();
});

// Featured movies
final featuredMoviesProvider = FutureProvider<List<Movie>>((ref) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get('${ApiConstants.movies}featured/');

  final List<dynamic> data = response.data;
  return data.map((json) => Movie.fromJson(json)).toList();
});

// Single movie detail
final movieDetailProvider = FutureProvider.family<Movie, int>((ref, movieId) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get('${ApiConstants.movies}$movieId/');
  return Movie.fromJson(response.data);
});

// Single series detail
final seriesDetailProvider = FutureProvider.family<Series, int>((ref, seriesId) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get('${ApiConstants.series}$seriesId/');
  return Series.fromJson(response.data);
});

// Search
final vodSearchQueryProvider = StateProvider<String>((ref) => '');

final filteredMoviesProvider = Provider<AsyncValue<List<Movie>>>((ref) {
  final moviesAsync = ref.watch(moviesProvider);
  final searchQuery = ref.watch(vodSearchQueryProvider).toLowerCase();

  return moviesAsync.whenData((movies) {
    if (searchQuery.isEmpty) return movies;

    return movies.where((movie) {
      return movie.title.toLowerCase().contains(searchQuery) ||
          (movie.originalTitle?.toLowerCase().contains(searchQuery) ?? false);
    }).toList();
  });
});
