import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/models/channel.dart';
import '../../../core/constants/api_constants.dart';

// Categories provider
final categoriesProvider = FutureProvider<List<Category>>((ref) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get(ApiConstants.categories);

  final List<dynamic> data = response.data['results'] ?? response.data;
  return data.map((json) => Category.fromJson(json)).toList();
});

// Selected category provider
final selectedCategoryProvider = StateProvider<int?>((ref) => null);

// Channels provider
final channelsProvider = FutureProvider<List<Channel>>((ref) async {
  final dio = ref.read(dioProvider);
  final categoryId = ref.watch(selectedCategoryProvider);

  String url = ApiConstants.channels;
  if (categoryId != null) {
    url += '?category=$categoryId';
  }

  final response = await dio.get(url);

  final List<dynamic> data = response.data['results'] ?? response.data;
  return data.map((json) => Channel.fromJson(json)).toList();
});

// Search query provider
final channelSearchQueryProvider = StateProvider<String>((ref) => '');

// Filtered channels provider
final filteredChannelsProvider = Provider<AsyncValue<List<Channel>>>((ref) {
  final channelsAsync = ref.watch(channelsProvider);
  final searchQuery = ref.watch(channelSearchQueryProvider).toLowerCase();

  return channelsAsync.whenData((channels) {
    if (searchQuery.isEmpty) return channels;

    return channels.where((channel) {
      return channel.name.toLowerCase().contains(searchQuery) ||
          channel.number.toString().contains(searchQuery);
    }).toList();
  });
});

// Favorites provider
final favoritesProvider = FutureProvider<List<Channel>>((ref) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get(ApiConstants.favorites);

  final List<dynamic> data = response.data['results'] ?? response.data;
  return data.map((json) => Channel.fromJson(json['channel'])).toList();
});

// Toggle favorite
final toggleFavoriteProvider = Provider((ref) {
  return (int channelId) async {
    final dio = ref.read(dioProvider);
    await dio.post(
      '${ApiConstants.favorites}toggle/',
      data: {'channel_id': channelId},
    );
    ref.invalidate(favoritesProvider);
  };
});

// Single channel provider
final channelProvider = FutureProvider.family<Channel, int>((ref, channelId) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get('${ApiConstants.channels}$channelId/');
  return Channel.fromJson(response.data);
});

// Channel stream URL provider
final channelStreamUrlProvider = FutureProvider.family<String, int>((ref, channelId) async {
  final dio = ref.read(dioProvider);
  final response = await dio.get('${ApiConstants.channels}$channelId/stream_url/');
  return response.data['url'];
});
