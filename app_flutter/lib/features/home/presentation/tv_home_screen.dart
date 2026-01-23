import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_theme.dart';
import '../../../core/widgets/tv_focusable.dart';

/// TV-optimized home screen with sidebar navigation
class TvHomeScreen extends ConsumerStatefulWidget {
  final Widget child;

  const TvHomeScreen({super.key, required this.child});

  @override
  ConsumerState<TvHomeScreen> createState() => _TvHomeScreenState();
}

class _TvHomeScreenState extends ConsumerState<TvHomeScreen> {
  int _selectedIndex = 0;
  bool _isSidebarExpanded = true;

  final _routes = ['/', '/epg', '/vod', '/recordings', '/settings'];
  final _labels = ['TV en Vivo', 'Guía', 'Películas', 'Grabaciones', 'Ajustes'];
  final _icons = [
    Icons.tv,
    Icons.calendar_today,
    Icons.movie,
    Icons.video_library,
    Icons.settings,
  ];

  void _onDestinationSelected(int index) {
    setState(() => _selectedIndex = index);
    context.go(_routes[index]);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final location = GoRouterState.of(context).matchedLocation;
    final index = _routes.indexOf(location);
    if (index != -1 && index != _selectedIndex) {
      setState(() => _selectedIndex = index);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Shortcuts(
      shortcuts: {
        // Toggle sidebar with Menu button
        LogicalKeySet(LogicalKeyboardKey.contextMenu): const ToggleSidebarIntent(),
        LogicalKeySet(LogicalKeyboardKey.f1): const ToggleSidebarIntent(),
      },
      child: Actions(
        actions: {
          ToggleSidebarIntent: CallbackAction<ToggleSidebarIntent>(
            onInvoke: (_) {
              setState(() => _isSidebarExpanded = !_isSidebarExpanded);
              return null;
            },
          ),
        },
        child: Scaffold(
          backgroundColor: AppColors.background,
          body: Row(
            children: [
              // Animated sidebar
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: _isSidebarExpanded ? 240 : 80,
                child: Container(
                  color: AppColors.surface,
                  child: Column(
                    children: [
                      // Logo
                      Padding(
                        padding: const EdgeInsets.all(20),
                        child: Row(
                          children: [
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                color: AppColors.primary.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.live_tv_rounded,
                                color: AppColors.primary,
                              ),
                            ),
                            if (_isSidebarExpanded) ...[
                              const SizedBox(width: 12),
                              const Text(
                                'QuattreTV',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),

                      const Divider(height: 1),
                      const SizedBox(height: 16),

                      // Navigation items
                      Expanded(
                        child: FocusTraversalGroup(
                          child: ListView.builder(
                            itemCount: _routes.length,
                            itemBuilder: (context, index) {
                              return _TvNavItem(
                                icon: _icons[index],
                                label: _labels[index],
                                isSelected: _selectedIndex == index,
                                isExpanded: _isSidebarExpanded,
                                autofocus: index == 0,
                                onSelect: () => _onDestinationSelected(index),
                              );
                            },
                          ),
                        ),
                      ),

                      // Collapse button
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: TvFocusable(
                          onSelect: () {
                            setState(() => _isSidebarExpanded = !_isSidebarExpanded);
                          },
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppColors.surfaceLight,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              _isSidebarExpanded
                                  ? Icons.chevron_left
                                  : Icons.chevron_right,
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Main content
              Expanded(child: widget.child),
            ],
          ),
        ),
      ),
    );
  }
}

class _TvNavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isSelected;
  final bool isExpanded;
  final bool autofocus;
  final VoidCallback onSelect;

  const _TvNavItem({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.isExpanded,
    this.autofocus = false,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: TvFocusable(
        autofocus: autofocus,
        onSelect: onSelect,
        borderRadius: BorderRadius.circular(12),
        focusScale: 1.05,
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: isExpanded ? 16 : 12,
            vertical: 14,
          ),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary.withOpacity(0.2) : null,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            mainAxisAlignment:
                isExpanded ? MainAxisAlignment.start : MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
                size: 24,
              ),
              if (isExpanded) ...[
                const SizedBox(width: 14),
                Text(
                  label,
                  style: TextStyle(
                    color: isSelected ? AppColors.primary : AppColors.textPrimary,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    fontSize: 15,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class ToggleSidebarIntent extends Intent {
  const ToggleSidebarIntent();
}
