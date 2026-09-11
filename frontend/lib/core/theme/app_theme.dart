import 'package:flutter/material.dart';

import 'console_colors.dart';

abstract final class AppTheme {
  static final light = ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: const Color(0xFFF3F5F9),
    colorScheme: ColorScheme.fromSeed(
      seedColor: const Color(0xFF3167E8),
      brightness: Brightness.light,
      surface: Colors.white,
    ),
    fontFamily: 'PingFang SC',
    textTheme: const TextTheme(
      bodyMedium: TextStyle(
        color: ConsoleColors.ink,
        fontSize: 14,
        height: 1.5,
      ),
      bodySmall: TextStyle(color: Color(0xFF8791A1), fontSize: 12),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFFFAFBFD),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
      hintStyle: const TextStyle(color: Color(0xFFA4AFBF), fontSize: 13),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(7),
        borderSide: const BorderSide(color: Color(0xFFE5EAF1)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(7),
        borderSide: const BorderSide(color: Color(0xFF7599F1), width: 1.5),
      ),
    ),
  );
}
