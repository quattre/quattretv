import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/platform_provider.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/channels/presentation/channel_list_screen.dart';
import '../../features/channels/presentation/tv_channel_list_screen.dart';
import '../../features/epg/presentation/epg_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/home/presentation/tv_home_screen.dart';
import '../../features/player/presentation/player_screen.dart';
import '../../features/player/presentation/tv_player_screen.dart';
import '../../features/pvr/presentation/recordings_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';
import '../../features/splash/presentation/splash_screen.dart';
import '../../features/vod/presentation/movie_detail_screen.dart';
import '../../features/vod/presentation/vod_screen.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authStateProvider);
  final isTV = ref.watch(isTvProvider);

  return GoRouter(
    initialLocation: '/splash',
    debugLogDiagnostics: true,
    redirect: (context, state) {
      final isLoggedIn = authState.valueOrNull?.isLoggedIn ?? false;
      final isLoggingIn = state.matchedLocation == '/login';
      final isSplash = state.matchedLocation == '/splash';

      if (isSplash) return null;

      if (!isLoggedIn && !isLoggingIn) {
        return '/login';
      }

      if (isLoggedIn && isLoggingIn) {
        return '/';
      }

      return null;
    },
    routes: [
      GoRoute(
        path: '/splash',
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      ShellRoute(
        builder: (context, state, child) {
          // Use TV or mobile home screen based on platform
          if (isTV) {
            return TvHomeScreen(child: child);
          }
          return HomeScreen(child: child);
        },
        routes: [
          GoRoute(
            path: '/',
            pageBuilder: (context, state) => NoTransitionPage(
              // Use TV or mobile channel list
              child: isTV
                  ? const TvChannelListScreen()
                  : const ChannelListScreen(),
            ),
          ),
          GoRoute(
            path: '/epg',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: EpgScreen(),
            ),
          ),
          GoRoute(
            path: '/vod',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: VodScreen(),
            ),
          ),
          GoRoute(
            path: '/recordings',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: RecordingsScreen(),
            ),
          ),
          GoRoute(
            path: '/settings',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: SettingsScreen(),
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/player/:channelId',
        builder: (context, state) {
          final channelId = state.pathParameters['channelId']!;
          final startTime = state.uri.queryParameters['startTime'];

          // Use TV or mobile player
          if (isTV) {
            return TvPlayerScreen(
              channelId: int.parse(channelId),
              startTime: startTime != null ? DateTime.parse(startTime) : null,
            );
          }

          return PlayerScreen(
            channelId: int.parse(channelId),
            startTime: startTime != null ? DateTime.parse(startTime) : null,
          );
        },
      ),
      GoRoute(
        path: '/movie/:movieId',
        builder: (context, state) {
          final movieId = state.pathParameters['movieId']!;
          return MovieDetailScreen(movieId: int.parse(movieId));
        },
      ),
    ],
  );
});
