import 'package:flutter/material.dart';

import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class ToolPanel extends StatelessWidget {
  const ToolPanel({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    final child = controller.tools.isEmpty
        ? emptyState(Icons.code_rounded, '暂无工具调用', '查看调用参数与返回结果')
        : ListView.separated(
            padding: EdgeInsets.zero,
            itemCount: controller.tools.length,
            separatorBuilder: (context, index) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final tool = controller.tools[index];
              return Container(
                decoration: BoxDecoration(
                  border: Border.all(color: const Color(0xFFE8EDF4)),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Theme(
                  data: Theme.of(
                    context,
                  ).copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    tilePadding: const EdgeInsets.symmetric(horizontal: 9),
                    childrenPadding: EdgeInsets.zero,
                    dense: true,
                    title: Text(
                      tool.name,
                      style: const TextStyle(
                        color: Color(0xFF62799B),
                        fontSize: 12,
                        fontFamily: 'monospace',
                      ),
                    ),
                    trailing: const Icon(
                      Icons.check_rounded,
                      size: 17,
                      color: Color(0xFF28A57D),
                    ),
                    children: [
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(9),
                        color: const Color(0xFFF8FAFF),
                        child: Text(
                          tool.payload,
                          style: const TextStyle(
                            color: Color(0xFF8798AE),
                            fontSize: 11,
                            height: 1.65,
                            fontFamily: 'monospace',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
    return executionPanel(
      title: coloredTitle(
        Icons.code_rounded,
        '工具调用',
        const Color(0xFFFFF5E6),
        const Color(0xFFCC9C4C),
      ),
      trailing: tag(
        '${controller.tools.length}',
        foreground: const Color(0xFF7D8DA4),
      ),
      child: child,
      footer: Row(
        children: [
          const Text('TOOLS'),
          const Spacer(),
          Text(
            controller.tools.isEmpty
                ? '尚未调用'
                : '${controller.tools.length} 次调用成功',
          ),
        ],
      ),
    );
  }
}
