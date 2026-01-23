import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/widgets/loading_widget.dart';
import '../../../core/widgets/error_widget.dart';
import '../providers/channels_provider.dart';
import '../../../core/api/models/channel.dart';

class ChannelListScreen extends ConsumerStatefulWidget {
  const ChannelListScreen({super.key});

  @override
  ConsumerState<ChannelListScreen> createState() => _ChannelListScreenState();
}

class _ChannelListScreenState extends ConsumerState<ChannelListScreen> {
  final _searchController = TextEditingController();
  bool _showSearch = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final categoriesAsync = ref.watch(categoriesProvider);
    final channelsAsync = ref.watch(filteredChannelsProvider);
    final selectedCategory = ref.watch(selectedCategoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: _showSearch
            ? TextField(
                controller: _searchController,
                autofocus: true,
                decoration: const InputDecoration(
                  hintText: 'Buscar canal...',
                  border: InputBorder.none,
                  hintStyle: TextStyle(color: AppColors.textMuted),
                ),
                style: const TextStyle(color: AppColors.textPrimary),
                onChanged: (value) {
                  ref.read(channelSearchQueryProvider.notifier).state = value;
                },
              )
            : const Text('TV en Vivo'),
        actions: [
          IconButton(
            icon: Icon(_showSearch ? Icons.close : Icons.search),
            onPressed: () {
              setState(() {
                _showSearch = !_showSearch;
                if (!_showSearch) {
                  _searchController.clear();
                  ref.read(channelSearchQueryProvider.notifier).state = '';
                }
              });
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(channelsProvider);
              ref.invalidate(categoriesProvider);
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Categories filter
          categoriesAsync.when(
            data: (categories) => SizedBox(
              height: 50,
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
                          ref.read(selectedCategoryProvider.notifier).state = null;
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
                        ref.read(selectedCategoryProvider.notifier).state =
                            selectedCategory == category.id ? null : category.id;
                      },
                      selectedColor: AppColors.primary.withOpacity(0.3),
                    ),
                  );
                },
              ),
            ),
            loading: () => const SizedBox(height: 50),
            error: (_, __) => const SizedBox(height: 50),
          ),

          // Channels grid
          Expanded(
            child: channelsAsync.when(
              data: (channels) {
                if (channels.isEmpty) {
                  return const Center(
                    child: Text(
                      'No hay canales disponibles',
                      style: TextStyle(color: AppColors.textMuted),
                    ),
                  );
                }

                return GridView.builder(
                  padding: const EdgeInsets.all(8),
                  gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
                    maxCrossAxisExtent: 180,
                    childAspectRatio: 0.85,
                    crossAxisSpacing: 8,
                    mainAxisSpacing: 8,
                  ),
                  itemCount: channels.length,
                  itemBuilder: (context, index) {
                    return ChannelCard(channel: channels[index]);
                  },
                );
              },
              loading: () => const LoadingWidget(),
              error: (error, _) => AppErrorWidget(
                message: error.toString(),
                onRetry: () => ref.invalidate(channelsProvider),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ChannelCard extends StatelessWidget {
  final Channel channel;

  const ChannelCard({super.key, required this.channel});

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push('/player/${channel.id}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Channel logo
            Expanded(
              flex: 3,
              child: Container(
                color: AppColors.surfaceLight,
                child: channel.logoUrl != null && channel.logoUrl!.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: channel.logoUrl!,
                        fit: BoxFit.contain,
                        placeholder: (_, __) => const Center(
                          child: Icon(
                            Icons.tv,
                            size: 40,
                            color: AppColors.textMuted,
                          ),
                        ),
                        errorWidget: (_, __, ___) => const Center(
                          child: Icon(
                            Icons.tv,
                            size: 40,
                            color: AppColors.textMuted,
                          ),
                        ),
                      )
                    : const Center(
                        child: Icon(
                          Icons.tv,
                          size: 40,
                          color: AppColors.textMuted,
                        ),
                      ),
              ),
            ),

            // Channel info
            Expanded(
              flex: 2,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Channel number and badges
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '${channel.number}',
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: AppColors.primary,
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        if (channel.isHd)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 4,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.hd.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'HD',
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.bold,
                                color: AppColors.hd,
                              ),
                            ),
                          ),
                        if (channel.is4k) ...[
                          const SizedBox(width: 2),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 4,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.fourK.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              '4K',
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.bold,
                                color: AppColors.fourK,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    // Channel name
                    Expanded(
                      child: Text(
                        channel.name,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: AppColors.textPrimary,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
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
}
