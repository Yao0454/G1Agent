import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';
import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class SkillPanel extends StatelessWidget {
  const SkillPanel({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    return executionPanel(
      title: coloredTitle(
        Icons.play_arrow_rounded,
        'Skill Executor',
        const Color(0xFFEEF4FF),
        const Color(0xFF608BEA),
      ),
      childPadding: const EdgeInsets.all(14),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '当前技能',
                        style: TextStyle(
                          color: Color(0xFF9AA3B2),
                          fontSize: 11,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        controller.skillName,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: ConsoleColors.ink,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                statusTag(controller.skillStatus),
              ],
            ),
            const SizedBox(height: 15),
            _step(0, '环境感知', '获取摄像头与场景信息'),
            _step(1, '任务规划', '解析指令并安排执行'),
            _step(2, '技能执行', '调用技能并反馈结果', last: true),
            const SizedBox(height: 4),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: controller.progress / 100,
                minHeight: 3,
                color: ConsoleColors.blue,
                backgroundColor: const Color(0xFFEDF1F7),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  controller.progressText,
                  style: const TextStyle(
                    color: Color(0xFFA0AABB),
                    fontSize: 11,
                  ),
                ),
                Text(
                  '${controller.progress}%',
                  style: const TextStyle(
                    color: Color(0xFFA0AABB),
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _step(int index, String title, String caption, {bool last = false}) {
    final done = controller.activeStep > index;
    final active = controller.activeStep == index && controller.busy;
    final circleColor = active
        ? ConsoleColors.blue
        : done
        ? const Color(0xFFEDF9F4)
        : const Color(0xFFF4F6FA);
    final borderColor = active
        ? ConsoleColors.blue
        : done
        ? const Color(0xFFDBF2E8)
        : const Color(0xFFE4E9F1);
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 20,
                height: 20,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: circleColor,
                  shape: BoxShape.circle,
                  border: Border.all(color: borderColor),
                ),
                child: done
                    ? const Icon(
                        Icons.check,
                        size: 12,
                        color: Color(0xFF30A57E),
                      )
                    : Text(
                        '${index + 1}',
                        style: TextStyle(
                          fontSize: 10,
                          fontFamily: 'monospace',
                          color: active
                              ? Colors.white
                              : const Color(0xFF8694A9),
                        ),
                      ),
              ),
              if (!last)
                Expanded(
                  child: Container(
                    width: 1,
                    margin: const EdgeInsets.symmetric(vertical: 2),
                    color: const Color(0xFFE3E8F1),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: last ? 10 : 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: active
                          ? ConsoleColors.blue
                          : const Color(0xFF56667B),
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 1),
                  Text(
                    caption,
                    style: const TextStyle(
                      color: Color(0xFFA9B2C0),
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
