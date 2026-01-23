import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Platform type enum
enum AppPlatform {
  mobile,
  tablet,
  tv,
  desktop,
  web,
}

/// Provider for current platform
final platformProvider = StateProvider<AppPlatform>((ref) {
  return AppPlatform.mobile; // Default, will be updated on init
});

/// Provider to check if running on TV
final isTvProvider = Provider<bool>((ref) {
  final platform = ref.watch(platformProvider);
  return platform == AppPlatform.tv;
});

/// Provider to check if large screen (tablet or TV)
final isLargeScreenProvider = Provider<bool>((ref) {
  final platform = ref.watch(platformProvider);
  return platform == AppPlatform.tv ||
      platform == AppPlatform.tablet ||
      platform == AppPlatform.desktop;
});

/// Platform detection utility
class PlatformDetector {
  /// Detect current platform based on screen size and OS
  static AppPlatform detect(double screenWidth, double screenHeight) {
    if (kIsWeb) {
      return screenWidth > 1200 ? AppPlatform.desktop : AppPlatform.mobile;
    }

    if (Platform.isAndroid || Platform.isIOS) {
      // Check if it's a TV (large screen, typically 10ft experience)
      final shortestSide = screenWidth < screenHeight ? screenWidth : screenHeight;
      final longestSide = screenWidth > screenHeight ? screenWidth : screenHeight;

      // TV detection heuristics:
      // - Very wide aspect ratio (16:9 or wider)
      // - Large screen (1920+ width in landscape)
      // - No typical tablet aspect ratio
      final aspectRatio = longestSide / shortestSide;

      if (aspectRatio >= 1.6 && longestSide >= 1280) {
        // Could be TV - check additional heuristics
        // In a real app, you'd use a platform channel to check leanback
        if (_isLikelyTV(longestSide, aspectRatio)) {
          return AppPlatform.tv;
        }
      }

      // Tablet: shortest side >= 600dp
      if (shortestSide >= 600) {
        return AppPlatform.tablet;
      }

      return AppPlatform.mobile;
    }

    if (Platform.isWindows || Platform.isMacOS || Platform.isLinux) {
      return AppPlatform.desktop;
    }

    return AppPlatform.mobile;
  }

  static bool _isLikelyTV(double longestSide, double aspectRatio) {
    // Heuristics for TV detection
    // TV screens are typically:
    // - 1920x1080 (Full HD)
    // - 3840x2160 (4K)
    // - 16:9 aspect ratio
    // - No touch interaction expected

    // This is a simplified check - in production, use platform channels
    return longestSide >= 1920 && aspectRatio >= 1.7 && aspectRatio <= 1.8;
  }

  /// Force TV mode (useful for testing)
  static void forceTvMode(WidgetRef ref) {
    ref.read(platformProvider.notifier).state = AppPlatform.tv;
  }

  /// Force mobile mode
  static void forceMobileMode(WidgetRef ref) {
    ref.read(platformProvider.notifier).state = AppPlatform.mobile;
  }
}

/// Extension for easy platform checks
extension PlatformCheck on WidgetRef {
  bool get isTV => read(isTvProvider);
  bool get isLargeScreen => read(isLargeScreenProvider);
  AppPlatform get platform => read(platformProvider);
}
