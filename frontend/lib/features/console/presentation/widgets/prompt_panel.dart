import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';
import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class PromptPanel extends StatelessWidget {
  const PromptPanel({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    return panel(
      header: sectionTitle(Icons.tune_rounded, '系统提示词'),
      trailing: tag(
        controller.promptSaved ? '已保存' : '未保存',
        foreground: controller.promptSaved
            ? const Color(0xFF8995A7)
            : const Color(0xFFBC8943),
        background: controller.promptSaved ? null : const Color(0xFFFFF4E8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              controller.cameraSource == 'local'
                  ? '视觉任务偏好（不能覆盖手势与安全约束）'
                  : '定义机器人的行为与约束',
              style: const TextStyle(color: Color(0xFF97A1B1), fontSize: 12),
            ),
            const SizedBox(height: 9),
            TextField(
              controller: controller.systemPromptController,
              minLines: 5,
              maxLines: 7,
              style: const TextStyle(
                color: Color(0xFF65748A),
                fontSize: 12,
                height: 1.65,
              ),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Text(
                  '${controller.systemPromptController.text.length} 字',
                  style: const TextStyle(
                    color: Color(0xFFA4AEBD),
                    fontSize: 11,
                  ),
                ),
                const Spacer(),
                TextButton(
                  onPressed: controller.savePrompt,
                  style: TextButton.styleFrom(
                    foregroundColor: ConsoleColors.blue,
                    padding: EdgeInsets.zero,
                    minimumSize: const Size(0, 30),
                  ),
                  child: const Text('保存配置  ↗', style: TextStyle(fontSize: 12)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
