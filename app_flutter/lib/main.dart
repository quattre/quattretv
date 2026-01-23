import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'core/config/app_router.dart';
import 'core/config/app_theme.dart';
import 'core/constants/storage_keys.dart';
import 'core/providers/platform_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Hive
  await Hive.initFlutter();
  await Hive.openBox(StorageKeys.settingsBox);
  await Hive.openBox(StorageKeys.cacheBox);

  // Set preferred orientations
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  // Set system UI overlay style
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );

  runApp(const ProviderScope(child: QuattreTVApp()));
}

class QuattreTVApp extends ConsumerStatefulWidget {
  const QuattreTVApp({super.key});

  @override
  ConsumerState<QuattreTVApp> createState() => _QuattreTVAppState();
}

class _QuattreTVAppState extends ConsumerState<QuattreTVApp> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Detect platform based on screen size
    final size = MediaQuery.of(context).size;
    final platform = PlatformDetector.detect(size.width, size.height);

    // Update platform provider after build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(platformProvider.notifier).state = platform;
    });
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(appRouterProvider);
    final isTV = ref.watch(isTvProvider);

    return MaterialApp.router(
      title: 'QuattreTV',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark,
      routerConfig: router,
      // TV-specific shortcuts
      shortcuts: isTV
          ? <ShortcutActivator, Intent>{
              ...WidgetsApp.defaultShortcuts,
              // Add TV remote shortcuts
              const SingleActivator(LogicalKeyboardKey.select):
                  const ActivateIntent(),
              const SingleActivator(LogicalKeyboardKey.goBack):
                  const DismissIntent(),
            }
          : null,
      builder: (context, child) {
        // Apply TV-specific settings
        if (isTV) {
          return MediaQuery(
            // Increase text scale for TV viewing distance
            data: MediaQuery.of(context).copyWith(
              textScaler: const TextScaler.linear(1.1),
            ),
            child: Focus(
              autofocus: true,
              child: child ?? const SizedBox(),
            ),
          );
        }
        return child ?? const SizedBox();
      },
    );
  }
}
