import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_theme.dart';
import '../../auth/providers/auth_provider.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);
    final user = authState.valueOrNull?.user;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Ajustes'),
      ),
      body: ListView(
        children: [
          // User info card
          if (user != null)
            Card(
              margin: const EdgeInsets.all(16),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 30,
                      backgroundColor: AppColors.primary,
                      child: Text(
                        user.username[0].toUpperCase(),
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            user.fullName,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          Text(
                            user.username,
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                            ),
                          ),
                          if (user.tariff != null) ...[
                            const SizedBox(height: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.primary.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                user.tariff!.name,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.primary,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // Subscription info
          if (user != null) ...[
            _SectionHeader(title: 'Suscripción'),
            _SettingsTile(
              icon: Icons.card_membership,
              title: 'Plan actual',
              subtitle: user.tariff?.name ?? 'Sin plan',
            ),
            _SettingsTile(
              icon: Icons.event,
              title: 'Expira',
              subtitle: user.subscriptionExpires != null
                  ? '${user.daysUntilExpiry} días restantes'
                  : 'No disponible',
              trailing: user.isSubscriptionActive
                  ? const Icon(Icons.check_circle, color: AppColors.success)
                  : const Icon(Icons.warning, color: AppColors.warning),
            ),
            _SettingsTile(
              icon: Icons.devices,
              title: 'Dispositivos',
              subtitle:
                  '${user.activeDevicesCount} de ${user.maxDevices} activos',
            ),
          ],

          // App settings
          _SectionHeader(title: 'Aplicación'),
          _SettingsTile(
            icon: Icons.language,
            title: 'Idioma',
            subtitle: 'Español',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.high_quality,
            title: 'Calidad de video',
            subtitle: 'Auto',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.family_restroom,
            title: 'Control parental',
            subtitle: 'Desactivado',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.notifications,
            title: 'Notificaciones',
            subtitle: 'Activadas',
            onTap: () {},
          ),

          // Player settings
          _SectionHeader(title: 'Reproductor'),
          SwitchListTile(
            secondary: const Icon(Icons.play_circle_outline),
            title: const Text('Reproducción automática'),
            subtitle: const Text('Reproducir siguiente canal'),
            value: true,
            onChanged: (value) {},
            activeColor: AppColors.primary,
          ),
          SwitchListTile(
            secondary: const Icon(Icons.subtitles),
            title: const Text('Subtítulos'),
            subtitle: const Text('Mostrar si están disponibles'),
            value: false,
            onChanged: (value) {},
            activeColor: AppColors.primary,
          ),

          // About
          _SectionHeader(title: 'Acerca de'),
          _SettingsTile(
            icon: Icons.info_outline,
            title: 'Versión',
            subtitle: '1.0.0',
          ),
          _SettingsTile(
            icon: Icons.description,
            title: 'Términos de servicio',
            onTap: () {},
          ),
          _SettingsTile(
            icon: Icons.privacy_tip,
            title: 'Política de privacidad',
            onTap: () {},
          ),

          // Logout
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: OutlinedButton.icon(
              onPressed: () async {
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Cerrar sesión'),
                    content: const Text(
                      '¿Estás seguro de que quieres cerrar sesión?',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Cancelar'),
                      ),
                      TextButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Cerrar sesión'),
                      ),
                    ],
                  ),
                );

                if (confirm == true) {
                  await ref.read(authStateProvider.notifier).logout();
                  if (context.mounted) {
                    context.go('/login');
                  }
                }
              },
              icon: const Icon(Icons.logout, color: AppColors.error),
              label: const Text(
                'Cerrar sesión',
                style: TextStyle(color: AppColors.error),
              ),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: AppColors.error),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;

  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: AppColors.textMuted,
          letterSpacing: 1,
        ),
      ),
    );
  }
}

class _SettingsTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;

  const _SettingsTile({
    required this.icon,
    required this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: AppColors.textSecondary),
      title: Text(title),
      subtitle: subtitle != null ? Text(subtitle!) : null,
      trailing: trailing ?? (onTap != null ? const Icon(Icons.chevron_right) : null),
      onTap: onTap,
    );
  }
}
