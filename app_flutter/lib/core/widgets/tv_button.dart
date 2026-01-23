import 'package:flutter/material.dart';

import '../config/app_theme.dart';
import 'tv_focusable.dart';

/// TV-optimized button with focus handling
class TvButton extends StatelessWidget {
  final String text;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool autofocus;
  final bool isPrimary;
  final double? width;
  final double height;

  const TvButton({
    super.key,
    required this.text,
    this.icon,
    this.onPressed,
    this.autofocus = false,
    this.isPrimary = true,
    this.width,
    this.height = 56,
  });

  @override
  Widget build(BuildContext context) {
    return TvFocusable(
      autofocus: autofocus,
      onSelect: onPressed,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: isPrimary ? AppColors.primary : AppColors.surface,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: width == null ? MainAxisSize.min : MainAxisSize.max,
          children: [
            if (icon != null) ...[
              Icon(icon, color: Colors.white),
              const SizedBox(width: 12),
            ],
            Padding(
              padding: EdgeInsets.symmetric(
                horizontal: icon != null ? 0 : 24,
              ),
              child: Text(
                text,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// TV-optimized icon button
class TvIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onPressed;
  final String? tooltip;
  final bool autofocus;
  final double size;

  const TvIconButton({
    super.key,
    required this.icon,
    this.onPressed,
    this.tooltip,
    this.autofocus = false,
    this.size = 48,
  });

  @override
  Widget build(BuildContext context) {
    return TvFocusable(
      autofocus: autofocus,
      onSelect: onPressed,
      borderRadius: BorderRadius.circular(size / 2),
      focusScale: 1.1,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: AppColors.surface,
          shape: BoxShape.circle,
        ),
        child: Icon(icon, color: Colors.white),
      ),
    );
  }
}

/// TV navigation rail item
class TvNavItem extends StatelessWidget {
  final IconData icon;
  final IconData? selectedIcon;
  final String label;
  final bool isSelected;
  final VoidCallback? onPressed;
  final bool autofocus;

  const TvNavItem({
    super.key,
    required this.icon,
    this.selectedIcon,
    required this.label,
    this.isSelected = false,
    this.onPressed,
    this.autofocus = false,
  });

  @override
  Widget build(BuildContext context) {
    return TvFocusable(
      autofocus: autofocus,
      onSelect: onPressed,
      borderRadius: BorderRadius.circular(12),
      focusColor: AppColors.primary,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.primary.withOpacity(0.2)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isSelected ? (selectedIcon ?? icon) : icon,
              color: isSelected ? AppColors.primary : AppColors.textSecondary,
            ),
            const SizedBox(width: 12),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
