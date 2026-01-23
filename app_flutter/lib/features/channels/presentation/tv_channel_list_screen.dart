import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/api/models/channel.dart';
import '../../../core/widgets/tv_focusable.dart';
import '../../../core/widgets/loading_widget.dart';
import '../providers/channels_provider.dart';
import '../../epg/providers/epg_provider.dart';

/// TV-optimized channel list with large tiles and D-pad navigation
class TvChannelListScreen extends ConsumerStatefulWidget {
  const TvChannelListScreen({super.key});

  @override
  ConsumerState<TvChannelListScreen> createState() => _TvChannelListScreenState();
}

class _TvChannelListScreenState extends ConsumerState<TvChannelListScreen> {
  final ScrollController _scrollController = ScrollController();
  int _focusedIndex = 0;

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToIndex(int index, int crossAxisCount, double itemHeight) {
    final row = index ~/ crossAxisCount;
    final offset = row * itemHeight;
    _scrollController.animateTo(
      offset,
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final channelsAsync = ref.watch(channelsProvider);
    final categoriesAsync = ref.watch(categoriesProvider);
    final selectedCategory = ref.watch(selectedCategoryProvider);

    final screenWidth = MediaQuery.of(context).size.width;
    final crossAxisCount = screenWidth > 1600 ? 6 : (screenWidth > 1200 ? 5 : 4);
    final itemWidth = (screenWidth - 300 - (crossAxisCount + 1) * 24) / crossAxisCount;
    final itemHeight = itemWidth * 0.85;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Row(
        children: [
          // Side navigation - Categories
          Container(
            width: 280,
            color: AppColors.surface,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Logo header
                Padding(
                  padding: const EdgeInsets.all(24),
                  child: Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: AppColors.primary.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(
                          Icons.live_tv_rounded,
                          color: AppColors.primary,
                          size: 28,
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'QuattreTV',
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1),

                // Categories list
                Expanded(
                  child: categoriesAsync.when(
                    data: (categories) => FocusTraversalGroup(
                      child: ListView(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        children: [
                          _TvCategoryItem(
                            name: 'Todos los canales',
                            icon: Icons.grid_view,
                            isSelected: selectedCategory == null,
                            onSelect: () {
                              ref.read(selectedCategoryProvider.notifier).state = null;
                            },
                            autofocus: true,
                          ),
                          _TvCategoryItem(
                            name: 'Favoritos',
                            icon: Icons.favorite,
                            isSelected: false,
                            onSelect: () {
                              // TODO: Show favorites
                            },
                          ),
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            child: Divider(),
                          ),
                          ...categories.map((cat) => _TvCategoryItem(
                                name: cat.name,
                                icon: Icons.folder,
                                isSelected: selectedCategory == cat.id,
                                onSelect: () {
                                  ref.read(selectedCategoryProvider.notifier).state =
                                      cat.id;
                                },
                              )),
                        ],
                      ),
                    ),
                    loading: () => const LoadingWidget(),
                    error: (_, __) => const SizedBox(),
                  ),
                ),
              ],
            ),
          ),

          // Main content - Channel grid
          Expanded(
            child: channelsAsync.when(
              data: (channels) {
                if (channels.isEmpty) {
                  return const Center(
                    child: Text(
                      'No hay canales disponibles',
                      style: TextStyle(fontSize: 20, color: AppColors.textMuted),
                    ),
                  );
                }

                return FocusTraversalGroup(
                  child: GridView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(24),
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: crossAxisCount,
                      crossAxisSpacing: 24,
                      mainAxisSpacing: 24,
                      childAspectRatio: 1 / 0.85,
                    ),
                    itemCount: channels.length,
                    itemBuilder: (context, index) {
                      return TvChannelCard(
                        channel: channels[index],
                        autofocus: index == 0 && selectedCategory == null,
                        onFocus: () {
                          setState(() => _focusedIndex = index);
                          _scrollToIndex(index, crossAxisCount, itemHeight + 24);
                        },
                      );
                    },
                  ),
                );
              },
              loading: () => const LoadingWidget(),
              error: (error, _) => Center(
                child: Text('Error: $error'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TvCategoryItem extends StatelessWidget {
  final String name;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onSelect;
  final bool autofocus;

  const _TvCategoryItem({
    required this.name,
    required this.icon,
    required this.isSelected,
    required this.onSelect,
    this.autofocus = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: TvFocusable(
        autofocus: autofocus,
        onSelect: onSelect,
        borderRadius: BorderRadius.circular(8),
        focusScale: 1.02,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary.withOpacity(0.2) : null,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              Icon(
                icon,
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
                size: 22,
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  name,
                  style: TextStyle(
                    color: isSelected ? AppColors.primary : AppColors.textPrimary,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    fontSize: 15,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class TvChannelCard extends ConsumerWidget {
  final Channel channel;
  final bool autofocus;
  final VoidCallback? onFocus;

  const TvChannelCard({
    super.key,
    required this.channel,
    this.autofocus = false,
    this.onFocus,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentProgramAsync = ref.watch(currentProgramProvider(channel.id));

    return TvFocusable(
      autofocus: autofocus,
      onSelect: () => context.push('/player/${channel.id}'),
      borderRadius: BorderRadius.circular(16),
      focusScale: 1.08,
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Logo area
            Expanded(
              flex: 3,
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight,
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(16),
                  ),
                ),
                padding: const EdgeInsets.all(20),
                child: channel.logoUrl != null && channel.logoUrl!.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: channel.logoUrl!,
                        fit: BoxFit.contain,
                        placeholder: (_, __) => _buildPlaceholder(),
                        errorWidget: (_, __, ___) => _buildPlaceholder(),
                      )
                    : _buildPlaceholder(),
              ),
            ),

            // Info area
            Expanded(
              flex: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Channel number and badges
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.primary,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            '${channel.number}',
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        if (channel.isHd)
                          _Badge(label: 'HD', color: AppColors.hd),
                        if (channel.is4k) ...[
                          const SizedBox(width: 4),
                          _Badge(label: '4K', color: AppColors.fourK),
                        ],
                        const Spacer(),
                        if (channel.hasTimeshift)
                          const Icon(
                            Icons.history,
                            size: 18,
                            color: AppColors.textMuted,
                          ),
                      ],
                    ),
                    const SizedBox(height: 10),

                    // Channel name
                    Text(
                      channel.name,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),

                    // Current program
                    const SizedBox(height: 4),
                    currentProgramAsync.when(
                      data: (program) => program != null
                          ? Text(
                              program.title,
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppColors.textSecondary,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            )
                          : const SizedBox(),
                      loading: () => const SizedBox(),
                      error: (_, __) => const SizedBox(),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlaceholder() {
    return const Center(
      child: Icon(
        Icons.tv,
        size: 48,
        color: AppColors.textMuted,
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;
  final Color color;

  const _Badge({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.bold,
          color: color,
        ),
      ),
    );
  }
}
