import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';
import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class ConsoleHeading extends StatelessWidget {
  const ConsoleHeading({
    super.key,
    required this.controller,
    required this.width,
  });

  final ConsoleController controller;
  final double width;

  @override
  Widget build(BuildContext context) {
    final mobile = width <= 640;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'G1 ROBOT WORKSPACE',
                style: TextStyle(
                  fontSize: mobile ? 8 : 10,
                  letterSpacing: mobile ? 1.5 : 2.2,
                  fontWeight: FontWeight.w700,
                  color: const Color(0xFF8190A5),
                ),
              ),
              const SizedBox(height: 4),
              Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: mobile ? 9 : 14,
                runSpacing: 4,
                children: [
                  Text(
                    '机器人控制台',
                    style: TextStyle(
                      fontSize: mobile ? 23 : 28,
                      fontWeight: FontWeight.w600,
                      letterSpacing: -0.6,
                    ),
                  ),
                  tag(
                    'G1-01',
                    foreground: const Color(0xFF708098),
                    background: Colors.transparent,
                  ),
                ],
              ),
              const SizedBox(height: 3),
              Text(
                '观察环境，发送指令，跟踪每一次执行。',
                style: TextStyle(
                  fontSize: mobile ? 10 : 13,
                  color: const Color(0xFF8B95A5),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              dot(
                controller.backend
                    ? ConsoleColors.green
                    : const Color(0xFFA4ADBB),
                glow: controller.backend,
              ),
              const SizedBox(width: 8),
              Text(
                controller.starting
                    ? '正在启动'
                    : controller.backend
                    ? '后端运行中'
                    : '后端未启动',
                style: TextStyle(
                  fontSize: mobile ? 10 : 12,
                  color: const Color(0xFF718096),
                ),
              ),
              if (!mobile) ...[
                const SizedBox(width: 16),
                Container(width: 1, height: 13, color: const Color(0xFFD8DFEB)),
                const SizedBox(width: 16),
                Text(
                  'SESSION  ${controller.sessionId}',
                  style: const TextStyle(
                    fontSize: 12,
                    fontFamily: 'monospace',
                    color: Color(0xFF718096),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
