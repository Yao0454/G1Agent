import 'package:flutter/material.dart';

import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class ModelPanel extends StatelessWidget {
  const ModelPanel({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    final content = controller.modelOutput.isEmpty
        ? emptyState('✧', '等待你的第一条指令', '模型的分析与执行结果将在这里显示')
        : SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF2F5FC),
                    borderRadius: BorderRadius.circular(5),
                  ),
                  child: Text(
                    controller.currentTask,
                    style: const TextStyle(
                      color: Color(0xFF60799E),
                      fontSize: 12,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'G1 AGENT · ${controller.isHardware ? 'HARDWARE' : 'SIMULATION'}',
                  style: const TextStyle(
                    color: Color(0xFFA295C6),
                    fontSize: 10,
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  controller.modelOutput,
                  style: const TextStyle(
                    color: Color(0xFF718097),
                    fontSize: 12,
                    height: 1.9,
                  ),
                ),
              ],
            ),
          );
    return executionPanel(
      title: coloredTitle(
        Icons.bolt_rounded,
        '模型输出',
        const Color(0xFFF2EFFE),
        const Color(0xFF9380D5),
      ),
      trailing: statusTag(controller.modelStatus),
      child: content,
      footer: Row(
        children: [
          dot(const Color(0xFFA896DE)),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              controller.cameraSource == 'local'
                  ? 'Video VLM / SkillRuntime'
                  : 'LangChain Agent / Ollama',
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '${(controller.modelDuration.inMilliseconds / 1000).toStringAsFixed(1)} s',
            style: const TextStyle(fontFamily: 'monospace'),
          ),
        ],
      ),
    );
  }
}
