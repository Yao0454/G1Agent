import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';

class ConsoleRail extends StatelessWidget {
  const ConsoleRail({super.key, required this.width});
  final double width;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(right: BorderSide(color: ConsoleColors.line)),
      ),
      child: Column(
        children: [
          const SizedBox(height: 22),
          Text.rich(
            const TextSpan(
              children: [
                TextSpan(
                  text: 'G',
                  style: TextStyle(color: Color(0xFF1C2C49)),
                ),
                TextSpan(
                  text: '1',
                  style: TextStyle(color: ConsoleColors.blue),
                ),
              ],
            ),
            style: const TextStyle(
              fontSize: 29,
              fontWeight: FontWeight.w900,
              letterSpacing: -2,
            ),
          ),
          const SizedBox(height: 34),
          _railItem(Icons.grid_view_rounded, '工作台', selected: true),
          const SizedBox(height: 10),
          _railItem(Icons.terminal_rounded, '日志'),
          const Spacer(),
          const Text(
            'v0.1',
            style: TextStyle(
              color: Color(0xFFA2AAB6),
              fontSize: 12,
              fontFamily: 'monospace',
            ),
          ),
          const SizedBox(height: 17),
          Container(
            width: 34,
            height: 34,
            alignment: Alignment.center,
            decoration: const BoxDecoration(
              color: Color(0xFFE9EDF5),
              shape: BoxShape.circle,
            ),
            child: const Text(
              'YF',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _railItem(IconData icon, String label, {bool selected = false}) {
    return Container(
      width: 62,
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        color: selected ? const Color(0xFFEEF3FF) : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        children: [
          Icon(
            icon,
            size: 21,
            color: selected ? ConsoleColors.blue : const Color(0xFF9099A7),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: selected ? ConsoleColors.blue : const Color(0xFF9099A7),
            ),
          ),
        ],
      ),
    );
  }
}
