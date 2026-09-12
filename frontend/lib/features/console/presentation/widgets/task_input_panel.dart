import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';
import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class TaskInputPanel extends StatelessWidget {
  const TaskInputPanel({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    return panel(
      header: sectionTitle(Icons.send_outlined, '输入提示词'),
      trailing: const Text(
        'Ctrl ↵',
        style: TextStyle(color: Color(0xFFA4AFBD), fontSize: 12),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: controller.taskController,
              minLines: 3,
              maxLines: 5,
              style: const TextStyle(
                color: Color(0xFF405069),
                fontSize: 13,
                height: 1.5,
              ),
              decoration: InputDecoration(
                hintText: controller.cameraSource == 'local'
                    ? '持续观察真实画面，回应握手、挥手或击掌。\n例如：有人向我挥手时，用中文回应。'
                    : '输入文本任务（模拟视频不会发送给视觉模型）。',
                fillColor: Colors.white,
              ),
            ),
            const SizedBox(height: 13),
            const Text(
              '试试这些指令',
              style: TextStyle(color: Color(0xFFA4AFBD), fontSize: 11),
            ),
            const SizedBox(height: 7),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                if (controller.cameraSource == 'local')
                  _suggestion('视觉交互', '持续观察手势，确认握手、挥手或击掌后回应，并简短说话。')
                else ...[
                  _suggestion('观察环境', '观察前方环境，识别障碍物。'),
                  _suggestion('向前移动', '向前移动 1 米，遇到障碍物停止。'),
                ],
                _suggestion('挥手问好', '向我挥手打个招呼。'),
              ],
            ),
            const SizedBox(height: 17),
            SizedBox(
              width: double.infinity,
              height: 44,
              child: FilledButton.icon(
                onPressed:
                    controller.backend &&
                        !controller.busy &&
                        controller.taskController.text.trim().isNotEmpty
                    ? controller.submitTask
                    : null,
                iconAlignment: IconAlignment.end,
                icon: const Icon(Icons.send_outlined, size: 16),
                label: Text(controller.cameraSource == 'local' ? '开始持续视觉交互' : '发送指令'),
                style: FilledButton.styleFrom(
                  backgroundColor: ConsoleColors.blue,
                  disabledBackgroundColor: const Color(0xFFA5BAE8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(7),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                !controller.backend
                    ? '请先启动后端服务'
                    : controller.busy
                    ? '任务执行中，可按 Esc 停止'
                    : controller.cameraSource == 'local'
                    ? '仅握手 / 挥手 / 击掌；持续运行至停止，不支持自由导航'
                    : 'Ctrl / ⌘ + Enter 发送指令',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFFA5AFBE), fontSize: 11),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _suggestion(String label, String prompt) {
    return OutlinedButton(
      onPressed: () {
        controller.taskController.text = prompt;
        controller.taskController.selection = TextSelection.collapsed(
          offset: prompt.length,
        );
      },
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFF7B8BA3),
        backgroundColor: const Color(0xFFF5F7FA),
        side: const BorderSide(color: Color(0xFFE9EDF3)),
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        minimumSize: const Size(0, 30),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
        textStyle: const TextStyle(fontSize: 11),
      ),
      child: Text(label),
    );
  }
}
