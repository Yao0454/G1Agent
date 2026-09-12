import 'package:flutter/services.dart';

import '../../models/console_log.dart';
import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';
import '../../controllers/console_controller.dart';
import 'console_widgets.dart';

class LogPanel extends StatelessWidget {
  const LogPanel({super.key, required this.controller, required this.width});

  final ConsoleController controller;
  final double width;

  @override
  Widget build(BuildContext context) {
    final mobile = width <= 640;
    return panel(
      headerHeight: null,
      header: Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 14,
        children: [
          sectionTitle(Icons.terminal_rounded, '运行日志'),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              dot(const Color(0xFF739DFF), glow: true),
              const SizedBox(width: 6),
              const Text(
                '实时',
                style: TextStyle(color: Color(0xFF7891B6), fontSize: 11),
              ),
            ],
          ),
          Text(
            '${controller.logs.length} 条',
            style: const TextStyle(color: Color(0xFFA0ACBC), fontSize: 11),
          ),
        ],
      ),
      trailing: Wrap(
        alignment: WrapAlignment.end,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 5,
        runSpacing: 6,
        children: [
          SizedBox(
            width: mobile ? 112 : 122,
            height: 34,
            child: DropdownButtonFormField<String>(
              initialValue: controller.logLevel,
              isDense: true,
              decoration: const InputDecoration(
                contentPadding: EdgeInsets.symmetric(
                  horizontal: 9,
                  vertical: 6,
                ),
                fillColor: Colors.white,
              ),
              style: const TextStyle(color: Color(0xFF64728A), fontSize: 11),
              items: const [
                DropdownMenuItem(value: 'ALL', child: Text('全部等级')),
                DropdownMenuItem(value: 'INFO', child: Text('INFO')),
                DropdownMenuItem(value: 'WARN', child: Text('WARN')),
                DropdownMenuItem(value: 'ERROR', child: Text('ERROR')),
                DropdownMenuItem(value: 'DEBUG', child: Text('DEBUG')),
              ],
              onChanged: (value) => controller.setLogLevel(value ?? 'ALL'),
            ),
          ),
          SizedBox(
            width: mobile ? 118 : 145,
            height: 34,
            child: TextField(
              controller: controller.searchController,
              style: const TextStyle(fontSize: 11),
              decoration: const InputDecoration(
                hintText: '搜索日志…',
                contentPadding: EdgeInsets.symmetric(
                  horizontal: 9,
                  vertical: 6,
                ),
                fillColor: Colors.white,
              ),
            ),
          ),
          _logAction('清空', controller.clearLogs),
          IconButton(
            tooltip: '复制全部日志',
            onPressed: () {
              final text = controller.logs
                  .map(
                    (e) =>
                        '[${e.time}] [${e.level}] [${e.source}] ${e.message}',
                  )
                  .join('\n');
              Clipboard.setData(ClipboardData(text: text));
              controller.onMessage('全部日志已复制到剪贴板');
            },
            icon: const Icon(
              Icons.download_outlined,
              size: 18,
              color: Color(0xFF8B99AD),
            ),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            height: mobile ? 210 : 180,
            color: const Color(0xFFFBFCFE),
            child: controller.visibleLogs.isEmpty
                ? const Center(
                    child: Text(
                      '暂无匹配的日志',
                      style: TextStyle(color: Color(0xFF97A4B9), fontSize: 12),
                    ),
                  )
                : ListView.builder(
                    controller: controller.logScrollController,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 18,
                      vertical: 10,
                    ),
                    itemCount: controller.visibleLogs.length,
                    itemBuilder: (context, index) =>
                        _logRow(controller.visibleLogs[index], mobile),
                  ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: ConsoleColors.line)),
            ),
            child: Row(
              children: [
                const Text(
                  '自动滚动至最新日志',
                  style: TextStyle(color: Color(0xFFA3AEC0), fontSize: 10),
                ),
                const Spacer(),
                if (!mobile)
                  Text(
                    'G1 CONSOLE / ${controller.isHardware ? 'HARDWARE' : 'SIMULATION'}',
                    style: const TextStyle(
                      color: Color(0xFFA3AEC0),
                      fontSize: 10,
                      fontFamily: 'monospace',
                      letterSpacing: .5,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _logRow(ConsoleLog entry, bool mobile) {
    final levelColor = switch (entry.level) {
      'INFO' => const Color(0xFF5986D0),
      'WARN' => const Color(0xFFC28B3C),
      'ERROR' => const Color(0xFFD46170),
      _ => const Color(0xFFA18ACB),
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: mobile ? 78 : 94,
            child: Text(
              entry.time,
              style: const TextStyle(
                color: Color(0xFFA2AEC0),
                fontSize: 11,
                fontFamily: 'monospace',
              ),
            ),
          ),
          SizedBox(
            width: mobile ? 48 : 54,
            child: Text(
              entry.level,
              style: TextStyle(
                color: levelColor,
                fontSize: 10,
                fontWeight: FontWeight.w600,
                fontFamily: 'monospace',
              ),
            ),
          ),
          if (!mobile)
            SizedBox(
              width: 92,
              child: Text(
                entry.source,
                style: const TextStyle(
                  color: Color(0xFF899BB8),
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
              ),
            ),
          Expanded(
            child: Text(
              entry.message,
              style: const TextStyle(
                color: Color(0xFF728099),
                fontSize: 11,
                fontFamily: 'monospace',
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _logAction(String label, VoidCallback action) {
    return TextButton(
      onPressed: action,
      style: TextButton.styleFrom(
        foregroundColor: const Color(0xFF8B99AD),
        padding: const EdgeInsets.symmetric(horizontal: 6),
        minimumSize: const Size(0, 32),
      ),
      child: Text(label, style: const TextStyle(fontSize: 11)),
    );
  }
}
