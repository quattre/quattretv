import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/api/models/movie.dart';
import '../../../core/widgets/loading_widget.dart';
import '../../../core/widgets/error_widget.dart';
import '../providers/vod_provider.dart';

class VodScreen extends ConsumerStatefulWidget {
  const VodScreen({super.key});

  @override
  ConsumerState<VodScreen> createState() => _VodScreenState();
}

class _VodScreenState extends ConsumerState<VodScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      ref.read(vodTypeProvider.notifier).state =
          _tabController.index == 0 ? VodType.movies : VodType.series;
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final categoriesAsync = ref.watch(vodCategoriesProvider);
    final selectedCategory = ref.watch(selectedVodCategoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Video On Demand'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Películas'),
            Tab(text: 'Series'),
          ],
          indicatorColor: AppColors.primary,
        ),
      ),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Buscar...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          ref.read(vodSearchQueryProvider.notifier).state = '';
                        },
                      )
                    : null,
              ),
              onChanged: (value) {
                ref.read(vodSearchQueryProvider.notifier).state = value;
              },
            ),
          ),

          // Categories
          categoriesAsync.when(
            data: (categories) => SizedBox(
              height: 40,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                itemCount: categories.length + 1,
                itemBuilder: (context, index) {
                  if (index == 0) {
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: FilterChip(
                        label: const Text('Todos'),
                        selected: selectedCategory == null,
                        onSelected: (_) {
                          ref.read(selectedVodCategoryProvider.notifier).state =
                              null;
                        },
                        selectedColor: AppColors.primary.withOpacity(0.3),
                      ),
                    );
                  }

                  final category = categories[index - 1];
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: FilterChip(
                      label: Text(category.name),
                      selected: selectedCategory == category.id,
                      onSelected: (_) {
                        ref.read(selectedVodCategoryProvider.notifier).state =
                            selectedCategory == category.id ? null : category.id;
                      },
                      selectedColor: AppColors.primary.withOpacity(0.3),
                    ),
                  );
                },
              ),
            ),
            loading: () => const SizedBox(height: 40),
            error: (_, __) => const SizedBox(height: 40),
          ),

          // Content
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _MoviesGrid(),
                _SeriesGrid(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MoviesGrid extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final moviesAsync = ref.watch(filteredMoviesProvider);

    return moviesAsync.when(
      data: (movies) {
        if (movies.isEmpty) {
          return const Center(
            child: Text(
              'No hay películas disponibles',
              style: TextStyle(color: AppColors.textMuted),
            ),
          );
        }

        return GridView.builder(
          padding: const EdgeInsets.all(8),
          gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 160,
            childAspectRatio: 0.65,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
          ),
          itemCount: movies.length,
          itemBuilder: (context, index) {
            return _MovieCard(movie: movies[index]);
          },
        );
      },
      loading: () => const LoadingWidget(),
      error: (error, _) => AppErrorWidget(
        message: error.toString(),
        onRetry: () => ref.invalidate(moviesProvider),
      ),
    );
  }
}

class _SeriesGrid extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final seriesAsync = ref.watch(seriesProvider);

    return seriesAsync.when(
      data: (series) {
        if (series.isEmpty) {
          return const Center(
            child: Text(
              'No hay series disponibles',
              style: TextStyle(color: AppColors.textMuted),
            ),
          );
        }

        return GridView.builder(
          padding: const EdgeInsets.all(8),
          gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 160,
            childAspectRatio: 0.65,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
          ),
          itemCount: series.length,
          itemBuilder: (context, index) {
            return _SeriesCard(series: series[index]);
          },
        );
      },
      loading: () => const LoadingWidget(),
      error: (error, _) => AppErrorWidget(
        message: error.toString(),
        onRetry: () => ref.invalidate(seriesProvider),
      ),
    );
  }
}

class _MovieCard extends StatelessWidget {
  final Movie movie;

  const _MovieCard({required this.movie});

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push('/movie/${movie.id}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Poster
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  movie.posterUrl != null && movie.posterUrl!.isNotEmpty
                      ? CachedNetworkImage(
                          imageUrl: movie.posterUrl!,
                          fit: BoxFit.cover,
                          placeholder: (_, __) => Container(
                            color: AppColors.surface,
                            child: const Icon(
                              Icons.movie,
                              color: AppColors.textMuted,
                            ),
                          ),
                          errorWidget: (_, __, ___) => Container(
                            color: AppColors.surface,
                            child: const Icon(
                              Icons.movie,
                              color: AppColors.textMuted,
                            ),
                          ),
                        )
                      : Container(
                          color: AppColors.surface,
                          child: const Icon(
                            Icons.movie,
                            color: AppColors.textMuted,
                          ),
                        ),
                  // Quality badge
                  if (movie.is4k || movie.isHd)
                    Positioned(
                      top: 4,
                      right: 4,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 4,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: movie.is4k
                              ? AppColors.fourK
                              : AppColors.hd,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          movie.is4k ? '4K' : 'HD',
                          style: const TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                  // Rating badge
                  if (movie.rating != null)
                    Positioned(
                      bottom: 4,
                      left: 4,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 4,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.star,
                              size: 12,
                              color: AppColors.warning,
                            ),
                            const SizedBox(width: 2),
                            Text(
                              movie.rating!.toStringAsFixed(1),
                              style: const TextStyle(
                                fontSize: 10,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
            // Info
            Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    movie.title,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (movie.year != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      '${movie.year}',
                      style: const TextStyle(
                        fontSize: 10,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SeriesCard extends StatelessWidget {
  final Series series;

  const _SeriesCard({required this.series});

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          // TODO: Navigate to series detail
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: series.posterUrl != null && series.posterUrl!.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: series.posterUrl!,
                      fit: BoxFit.cover,
                    )
                  : Container(
                      color: AppColors.surface,
                      child: const Icon(
                        Icons.tv,
                        color: AppColors.textMuted,
                      ),
                    ),
            ),
            Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    series.title,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${series.seasonsCount} temporadas',
                    style: const TextStyle(
                      fontSize: 10,
                      color: AppColors.textMuted,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
