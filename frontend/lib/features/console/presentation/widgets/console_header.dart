import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';
import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class ConsoleHeader extends StatelessWidget {
  const ConsoleHeader({
    super.key,
    required this.controller,
    required this.width,
  });

  final ConsoleController controller;
  final double width;

  @override
  Widget build(BuildContext context) {
    final mobile = width <= 640;
    return Container(
      height: mobile ? 55 : 72,
      padding: EdgeInsets.symmetric(horizontal: mobile ? 16 : 32),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: ConsoleColors.line)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text.rich(
              TextSpan(
                children: [
                  const TextSpan(
                    text: '机器人工作空间',
                    style: TextStyle(color: Color(0xFF8B94A2)),
                  ),
                  TextSpan(
                    text: mobile ? '  /  ' : '     /     ',
                    style: const TextStyle(color: Color(0xFFC1C7D0)),
                  ),
                  const TextSpan(
                    text: '运行工作台',
                    style: TextStyle(
                      color: Color(0xFF445168),
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: mobile ? 11 : 13),
            ),
          ),
          tag(
            controller.isHardware ? 'HARDWARE · 真机模式' : 'SIMULATION · 模拟模式',
            foreground: const Color(0xFF4D6B9A),
            background: const Color(0xFFF0F4FA),
          ),
          if (!mobile) ...[
            const SizedBox(width: 23),
            Text(
              controller.formattedTime(),
              style: const TextStyle(
                color: Color(0xFF6F7E91),
                fontFamily: 'monospace',
                fontSize: 12,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
