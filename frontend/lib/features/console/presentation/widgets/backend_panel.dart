import 'package:flutter/material.dart';

import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class BackendPanel extends StatelessWidget {
  const BackendPanel({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    return panel(
      paddingHeader: false,
      child: Padding(
        padding: const EdgeInsets.all(19),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '后端服务',
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 14,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        controller.backend
                            ? '${controller.isHardware ? '真机' : '模拟'}服务已就绪，等待任务调度'
                            : controller.connectedToApi
                            ? '启动后即可发送任务指令'
                            : '等待连接 FastAPI 服务',
                        style: const TextStyle(
                          color: Color(0xFF9BA5B5),
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  width: 9,
                  height: 9,
                  decoration: BoxDecoration(
                    color: controller.backend
                        ? const Color(0xFF28AD85)
                        : const Color(0xFFB2BDCC),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: controller.backend
                            ? const Color(0xFFECF8F3)
                            : const Color(0xFFF3F5F8),
                        spreadRadius: 5,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              height: 44,
              child: OutlinedButton.icon(
                onPressed: controller.starting
                    ? null
                    : controller.toggleBackend,
                icon: Icon(
                  controller.backend
                      ? Icons.stop_rounded
                      : Icons.play_arrow_rounded,
                  size: 17,
                ),
                label: Text(
                  controller.starting
                      ? '正在启动…'
                      : controller.backend
                      ? '停止后端'
                      : '启动后端',
                ),
                style: OutlinedButton.styleFrom(
                  foregroundColor: controller.backend
                      ? const Color(0xFF63728B)
                      : const Color(0xFF3970E5),
                  backgroundColor: controller.backend
                      ? const Color(0xFFF4F6F9)
                      : const Color(0xFFEDF3FF),
                  side: BorderSide(
                    color: controller.backend
                        ? const Color(0xFFE5EAF1)
                        : const Color(0xFFDCE7FF),
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(7),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            _serviceLine(
              '连接方式',
              controller.isHardware ? 'Unitree G1' : '本地模拟器',
            ),
            const SizedBox(height: 7),
            _serviceLine(
              '服务状态',
              controller.starting
                  ? '初始化中'
                  : controller.backend
                  ? '运行中 · ${controller.isHardware ? '真机' : '模拟'}'
                  : controller.connectedToApi
                  ? 'API 在线 · 会话未启动'
                  : 'API 未连接',
            ),
          ],
        ),
      ),
    );
  }

  Widget _serviceLine(String name, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          name,
          style: const TextStyle(color: Color(0xFF9EA8B8), fontSize: 11),
        ),
        Text(
          value,
          style: const TextStyle(color: Color(0xFF74829A), fontSize: 11),
        ),
      ],
    );
  }
}
