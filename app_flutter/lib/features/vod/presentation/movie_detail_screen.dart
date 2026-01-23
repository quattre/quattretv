import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/widgets/loading_widget.dart';
import '../providers/vod_provider.dart';

class MovieDetailScreen extends ConsumerWidget {
  final int movieId;

  const MovieDetailScreen({super.key, required this.movieId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final movieAsync = ref.watch(movieDetailProvider(movieId));

    return Scaffold(
      body: movieAsync.when(
        data: (movie) => CustomScrollView(
          slivers: [
            // App bar with backdrop
            SliverAppBar(
              expandedHeight: 300,
              pinned: true,
              flexibleSpace: FlexibleSpaceBar(
                background: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (movie.backdropUrl != null)
                      CachedNetworkImage(
                        imageUrl: movie.backdropUrl!,
                        fit: BoxFit.cover,
                      )
                    else if (movie.posterUrl != null)
                      CachedNetworkImage(
                        imageUrl: movie.posterUrl!,
                        fit: BoxFit.cover,
                      )
                    else
                      Container(color: AppColors.surface),
                    // Gradient overlay
                    Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            Colors.transparent,
                            AppColors.background.withOpacity(0.8),
                            AppColors.background,
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Content
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Title
                    Text(
                      movie.title,
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    if (movie.originalTitle != null &&
                        movie.originalTitle != movie.title) ...[
                      const SizedBox(height: 4),
                      Text(
                        movie.originalTitle!,
                        style: const TextStyle(
                          fontSize: 16,
                          color: AppColors.textSecondary,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ],

                    const SizedBox(height: 16),

                    // Metadata row
                    Wrap(
                      spacing: 16,
                      runSpacing: 8,
                      children: [
                        if (movie.year != null)
                          _MetadataChip(
                            icon: Icons.calendar_today,
                            label: '${movie.year}',
                          ),
                        if (movie.duration != null)
                          _MetadataChip(
                            icon: Icons.access_time,
                            label: movie.durationFormatted,
                          ),
                        if (movie.rating != null)
                          _MetadataChip(
                            icon: Icons.star,
                            label: movie.rating!.toStringAsFixed(1),
                            iconColor: AppColors.warning,
                          ),
                        if (movie.isHd)
                          const _MetadataChip(
                            icon: Icons.hd,
                            label: 'HD',
                            iconColor: AppColors.hd,
                          ),
                        if (movie.is4k)
                          const _MetadataChip(
                            icon: Icons.four_k,
                            label: '4K',
                            iconColor: AppColors.fourK,
                          ),
                      ],
                    ),

                    const SizedBox(height: 24),

                    // Play button
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: () {
                          // TODO: Play movie
                        },
                        icon: const Icon(Icons.play_arrow),
                        label: const Text('Reproducir'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                        ),
                      ),
                    ),

                    if (movie.trailerUrl != null) ...[
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () {
                            // TODO: Play trailer
                          },
                          icon: const Icon(Icons.play_circle_outline),
                          label: const Text('Ver tráiler'),
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 16),
                          ),
                        ),
                      ),
                    ],

                    const SizedBox(height: 24),

                    // Description
                    if (movie.description != null &&
                        movie.description!.isNotEmpty) ...[
                      const Text(
                        'Sinopsis',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        movie.description!,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          height: 1.5,
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],

                    // Genres
                    if (movie.genreList.isNotEmpty) ...[
                      const Text(
                        'Géneros',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: movie.genreList
                            .map((genre) => Chip(
                                  label: Text(genre),
                                  backgroundColor: AppColors.surface,
                                ))
                            .toList(),
                      ),
                      const SizedBox(height: 24),
                    ],

                    // Director
                    if (movie.director != null &&
                        movie.director!.isNotEmpty) ...[
                      const Text(
                        'Director',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        movie.director!,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],

                    // Cast
                    if (movie.cast != null && movie.cast!.isNotEmpty) ...[
                      const Text(
                        'Reparto',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        movie.cast!,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],

                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ),
          ],
        ),
        loading: () => const LoadingWidget(),
        error: (error, _) => Center(child: Text('Error: $error')),
      ),
    );
  }
}

class _MetadataChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color? iconColor;

  const _MetadataChip({
    required this.icon,
    required this.label,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: iconColor ?? AppColors.textSecondary),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
