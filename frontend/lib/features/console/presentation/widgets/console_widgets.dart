import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';

Widget panel({
  Widget? header,
  Widget? trailing,
  required Widget child,
  bool paddingHeader = true,
  double? headerHeight = 57,
}) {
  return Container(
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      color: Colors.white,
      border: Border.all(color: const Color(0xFFE3E8F0)),
      borderRadius: BorderRadius.circular(12),
      boxShadow: const [
        BoxShadow(
          color: Color(0x03000000),
          blurRadius: 8,
          offset: Offset(0, 3),
        ),
      ],
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (paddingHeader && header != null)
          Container(
            constraints: BoxConstraints(minHeight: headerHeight ?? 54),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: ConsoleColors.line)),
            ),
            child: Row(
              children: [
                Expanded(child: header),
                if (trailing != null) ...[
                  const SizedBox(width: 10),
                  Flexible(child: trailing),
                ],
              ],
            ),
          ),
        child,
      ],
    ),
  );
}

Widget executionPanel({
  required Widget title,
  Widget? trailing,
  required Widget child,
  Widget? footer,
  EdgeInsets childPadding = const EdgeInsets.all(14),
}) {
  return SizedBox(
    height: 352,
    child: panel(
      header: title,
      trailing: trailing,
      child: Expanded(
        child: Column(
          children: [
            Expanded(
              child: Padding(padding: childPadding, child: child),
            ),
            if (footer != null)
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 9,
                ),
                decoration: const BoxDecoration(
                  border: Border(top: BorderSide(color: ConsoleColors.line)),
                ),
                child: DefaultTextStyle(
                  style: const TextStyle(
                    color: Color(0xFF99A3B2),
                    fontSize: 10,
                  ),
                  child: footer,
                ),
              ),
          ],
        ),
      ),
    ),
  );
}

Widget sectionTitle(IconData icon, String title) {
  return Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 19, color: const Color(0xFF7B89A0)),
      const SizedBox(width: 9),
      Text(
        title,
        style: const TextStyle(
          color: ConsoleColors.ink,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),
    ],
  );
}

Widget coloredTitle(
  IconData icon,
  String title,
  Color background,
  Color foreground,
) {
  return Row(
    children: [
      Container(
        width: 23,
        height: 23,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Icon(icon, color: foreground, size: 15),
      ),
      const SizedBox(width: 7),
      Text(
        title,
        style: const TextStyle(
          color: ConsoleColors.ink,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),
    ],
  );
}

Widget tag(
  String text, {
  Color foreground = const Color(0xFF8995A7),
  Color? background,
}) {
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
    decoration: BoxDecoration(
      color: background ?? const Color(0xFFF5F7FA),
      border: Border.all(color: const Color(0xFFE4EAF2)),
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      text,
      style: TextStyle(
        color: foreground,
        fontSize: 11,
        letterSpacing: text.contains('DEMO') ? .7 : 0,
      ),
    ),
  );
}

Widget statusTag(String status) {
  if (status == 'RUNNING' || status == '生成中') {
    return tag(
      status,
      foreground: const Color(0xFF497FDA),
      background: const Color(0xFFEDF4FF),
    );
  }
  if (status == 'DONE' || status == '已完成') {
    return tag(
      status,
      foreground: const Color(0xFF30A57E),
      background: const Color(0xFFEDF9F4),
    );
  }
  if (status == 'STOPPED' || status == '已停止') {
    return tag(
      status,
      foreground: const Color(0xFFBC8943),
      background: const Color(0xFFFFF4E8),
    );
  }
  return tag(status);
}

Widget dot(Color color, {bool glow = false}) {
  return Container(
    width: 6,
    height: 6,
    decoration: BoxDecoration(
      color: color,
      shape: BoxShape.circle,
      boxShadow: glow
          ? [BoxShadow(color: color.withValues(alpha: .16), spreadRadius: 3)]
          : null,
    ),
  );
}

Widget darkChip(String text) {
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
    decoration: BoxDecoration(
      color: const Color(0xFF101B2C).withValues(alpha: .70),
      border: Border.all(color: const Color(0xFFC2D5FF).withValues(alpha: .09)),
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      text,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(
        color: Color(0xFF93A9C8),
        fontSize: 10,
        fontFamily: 'monospace',
        letterSpacing: .3,
      ),
    ),
  );
}

Widget glassButton(IconData icon, String tooltip, VoidCallback action) {
  return Tooltip(
    message: tooltip,
    child: InkWell(
      onTap: action,
      borderRadius: BorderRadius.circular(5),
      child: Container(
        width: 32,
        height: 30,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: const Color(0xFF17243B).withValues(alpha: .78),
          border: Border.all(
            color: const Color(0xFFC4D6F9).withValues(alpha: .13),
          ),
          borderRadius: BorderRadius.circular(5),
        ),
        child: Icon(icon, size: 16, color: const Color(0xFFA8BAD3)),
      ),
    ),
  );
}

Widget emptyState(Object icon, String title, String caption) {
  return Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        icon is IconData
            ? Icon(icon, color: const Color(0xFFB1BDCE), size: 25)
            : Text(
                icon.toString(),
                style: const TextStyle(color: Color(0xFFBEC5D9), fontSize: 32),
              ),
        const SizedBox(height: 8),
        Text(
          title,
          textAlign: TextAlign.center,
          style: const TextStyle(color: Color(0xFF9AA5B5), fontSize: 12),
        ),
        const SizedBox(height: 6),
        Text(
          caption,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Color(0xFFADB5C1),
            fontSize: 11,
            height: 1.6,
          ),
        ),
      ],
    ),
  );
}
