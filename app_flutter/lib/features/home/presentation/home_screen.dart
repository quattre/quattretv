import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_theme.dart';

class HomeScreen extends ConsumerStatefulWidget {
  final Widget child;

  const HomeScreen({super.key, required this.child});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  int _selectedIndex = 0;

  final _routes = ['/', '/epg', '/vod', '/recordings', '/settings'];

  void _onDestinationSelected(int index) {
    setState(() => _selectedIndex = index);
    context.go(_routes[index]);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Update selected index based on current route
    final location = GoRouterState.of(context).matchedLocation;
    final index = _routes.indexOf(location);
    if (index != -1 && index != _selectedIndex) {
      setState(() => _selectedIndex = index);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width > 800;

    if (isWide) {
      // Tablet/Desktop layout with navigation rail
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: _selectedIndex,
              onDestinationSelected: _onDestinationSelected,
              backgroundColor: AppColors.surface,
              indicatorColor: AppColors.primary.withOpacity(0.2),
              labelType: NavigationRailLabelType.all,
              leading: Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Column(
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
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'QuattreTV',
                      style: TextStyle(
                        fontSize: 10,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              destinations: const [
                NavigationRailDestination(
                  icon: Icon(Icons.tv_outlined),
                  selectedIcon: Icon(Icons.tv),
                  label: Text('TV'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.calendar_today_outlined),
                  selectedIcon: Icon(Icons.calendar_today),
                  label: Text('Guía'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.movie_outlined),
                  selectedIcon: Icon(Icons.movie),
                  label: Text('VOD'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.video_library_outlined),
                  selectedIcon: Icon(Icons.video_library),
                  label: Text('Grabaciones'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.settings_outlined),
                  selectedIcon: Icon(Icons.settings),
                  label: Text('Ajustes'),
                ),
              ],
            ),
            const VerticalDivider(width: 1, thickness: 1),
            Expanded(child: widget.child),
          ],
        ),
      );
    }

    // Mobile layout with bottom navigation
    return Scaffold(
      body: widget.child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _onDestinationSelected,
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.primary.withOpacity(0.2),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.tv_outlined),
            selectedIcon: Icon(Icons.tv),
            label: 'TV',
          ),
          NavigationDestination(
            icon: Icon(Icons.calendar_today_outlined),
            selectedIcon: Icon(Icons.calendar_today),
            label: 'Guía',
          ),
          NavigationDestination(
            icon: Icon(Icons.movie_outlined),
            selectedIcon: Icon(Icons.movie),
            label: 'VOD',
          ),
          NavigationDestination(
            icon: Icon(Icons.video_library_outlined),
            selectedIcon: Icon(Icons.video_library),
            label: 'Grabaciones',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Ajustes',
          ),
        ],
      ),
    );
  }
}
