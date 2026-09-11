import 'package:flutter/material.dart';

import '../../controllers/console_controller.dart';

class StopTaskButton extends StatelessWidget {
  const StopTaskButton({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 44,
      child: OutlinedButton(
        onPressed: controller.busy ? controller.cancelTask : null,
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFFBD6F79),
          backgroundColor: const Color(0xFFFFF6F6),
          disabledForegroundColor: const Color(
            0xFFBD6F79,
          ).withValues(alpha: .45),
          side: const BorderSide(color: Color(0xFFEADADD)),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(7)),
        ),
        child: Row(
          children: [
            const Icon(Icons.stop_circle_outlined, size: 16),
            const Expanded(
              child: Center(
                child: Text('停止执行', style: TextStyle(fontSize: 12)),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFFE7CFD3)),
                borderRadius: BorderRadius.circular(3),
              ),
              child: const Text(
                'ESC',
                style: TextStyle(fontFamily: 'monospace', fontSize: 10),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
