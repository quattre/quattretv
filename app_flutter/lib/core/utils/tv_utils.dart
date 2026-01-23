import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Utility class for TV-specific functionality
class TvUtils {
  static bool? _isTV;

  /// Check if running on Android TV
  static Future<bool> isAndroidTV() async {
    if (_isTV != null) return _isTV!;

    if (!Platform.isAndroid) {
      _isTV = false;
      return false;
    }

    try {
      const platform = MethodChannel('quattretv/platform');
      _isTV = await platform.invokeMethod<bool>('isTV') ?? false;
    } catch (e) {
      // Fallback: check if it's a large screen without touch
      _isTV = false;
    }

    return _isTV!;
  }

  /// Check if running on any TV platform
  static bool get isTV {
    // Simple heuristic based on platform
    if (kIsWeb) return false;
    return _isTV ?? false;
  }
}

/// TV-optimized focus handling
class TvFocusUtils {
  /// Request focus for a node
  static void requestFocus(FocusNode node) {
    if (!node.hasFocus) {
      node.requestFocus();
    }
  }

  /// Move focus in a direction
  static void moveFocus(BuildContext context, TraversalDirection direction) {
    FocusScope.of(context).focusInDirection(direction);
  }
}

/// Extension to check TV mode easily
extension TvContext on BuildContext {
  bool get isTV => TvUtils.isTV;
}
