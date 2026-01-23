import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../config/app_theme.dart';

/// A widget that handles TV remote/D-pad focus
class TvFocusable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onSelect;
  final VoidCallback? onLongPress;
  final bool autofocus;
  final FocusNode? focusNode;
  final double focusScale;
  final Color? focusColor;
  final BorderRadius? borderRadius;
  final EdgeInsets focusPadding;

  const TvFocusable({
    super.key,
    required this.child,
    this.onSelect,
    this.onLongPress,
    this.autofocus = false,
    this.focusNode,
    this.focusScale = 1.05,
    this.focusColor,
    this.borderRadius,
    this.focusPadding = EdgeInsets.zero,
  });

  @override
  State<TvFocusable> createState() => _TvFocusableState();
}

class _TvFocusableState extends State<TvFocusable>
    with SingleTickerProviderStateMixin {
  late FocusNode _focusNode;
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;
  bool _isFocused = false;

  @override
  void initState() {
    super.initState();
    _focusNode = widget.focusNode ?? FocusNode();

    _animationController = AnimationController(
      duration: const Duration(milliseconds: 150),
      vsync: this,
    );

    _scaleAnimation = Tween<double>(
      begin: 1.0,
      end: widget.focusScale,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOut,
    ));
  }

  @override
  void dispose() {
    if (widget.focusNode == null) {
      _focusNode.dispose();
    }
    _animationController.dispose();
    super.dispose();
  }

  void _handleFocusChange(bool hasFocus) {
    setState(() => _isFocused = hasFocus);

    if (hasFocus) {
      _animationController.forward();
    } else {
      _animationController.reverse();
    }
  }

  KeyEventResult _handleKeyEvent(FocusNode node, KeyEvent event) {
    if (event is KeyDownEvent) {
      // Handle Enter/Select button
      if (event.logicalKey == LogicalKeyboardKey.select ||
          event.logicalKey == LogicalKeyboardKey.enter ||
          event.logicalKey == LogicalKeyboardKey.gameButtonA) {
        widget.onSelect?.call();
        return KeyEventResult.handled;
      }

      // Handle long press simulation with dedicated button
      if (event.logicalKey == LogicalKeyboardKey.contextMenu ||
          event.logicalKey == LogicalKeyboardKey.gameButtonX) {
        widget.onLongPress?.call();
        return KeyEventResult.handled;
      }
    }

    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    return Focus(
      focusNode: _focusNode,
      autofocus: widget.autofocus,
      onFocusChange: _handleFocusChange,
      onKeyEvent: _handleKeyEvent,
      child: GestureDetector(
        onTap: widget.onSelect,
        onLongPress: widget.onLongPress,
        child: AnimatedBuilder(
          animation: _scaleAnimation,
          builder: (context, child) {
            return Transform.scale(
              scale: _scaleAnimation.value,
              child: Container(
                padding: widget.focusPadding,
                decoration: BoxDecoration(
                  borderRadius: widget.borderRadius ?? BorderRadius.circular(12),
                  border: _isFocused
                      ? Border.all(
                          color: widget.focusColor ?? AppColors.primary,
                          width: 3,
                        )
                      : null,
                  boxShadow: _isFocused
                      ? [
                          BoxShadow(
                            color: (widget.focusColor ?? AppColors.primary)
                                .withOpacity(0.4),
                            blurRadius: 20,
                            spreadRadius: 2,
                          ),
                        ]
                      : null,
                ),
                child: widget.child,
              ),
            );
          },
        ),
      ),
    );
  }
}

/// A row of focusable items for TV navigation
class TvFocusableRow extends StatelessWidget {
  final List<Widget> children;
  final MainAxisAlignment mainAxisAlignment;
  final CrossAxisAlignment crossAxisAlignment;
  final double spacing;

  const TvFocusableRow({
    super.key,
    required this.children,
    this.mainAxisAlignment = MainAxisAlignment.start,
    this.crossAxisAlignment = CrossAxisAlignment.center,
    this.spacing = 16,
  });

  @override
  Widget build(BuildContext context) {
    return FocusTraversalGroup(
      policy: OrderedTraversalPolicy(),
      child: Row(
        mainAxisAlignment: mainAxisAlignment,
        crossAxisAlignment: crossAxisAlignment,
        children: children
            .map((child) => Padding(
                  padding: EdgeInsets.only(right: spacing),
                  child: child,
                ))
            .toList(),
      ),
    );
  }
}

/// A grid optimized for TV navigation
class TvFocusableGrid extends StatelessWidget {
  final int crossAxisCount;
  final List<Widget> children;
  final double spacing;
  final double childAspectRatio;

  const TvFocusableGrid({
    super.key,
    required this.crossAxisCount,
    required this.children,
    this.spacing = 16,
    this.childAspectRatio = 1.0,
  });

  @override
  Widget build(BuildContext context) {
    return FocusTraversalGroup(
      policy: OrderedTraversalPolicy(),
      child: GridView.builder(
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: crossAxisCount,
          crossAxisSpacing: spacing,
          mainAxisSpacing: spacing,
          childAspectRatio: childAspectRatio,
        ),
        itemCount: children.length,
        itemBuilder: (context, index) => children[index],
      ),
    );
  }
}
