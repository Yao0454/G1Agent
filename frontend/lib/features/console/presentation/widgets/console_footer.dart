import 'package:flutter/material.dart';

import '../../controllers/console_controller.dart';

class ConsoleFooter extends StatelessWidget {
  const ConsoleFooter({
    super.key,
    required this.controller,
    required this.width,
  });

  final ConsoleController controller;
  final double width;

  @override
  Widget build(BuildContext context) {
    final mobile = width <= 640;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: mobile
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'G1 · Robot Control Console',
                  style: TextStyle(color: Color(0xFFA9B2C0), fontSize: 10),
                ),
                SizedBox(height: 5),
                Text(
                  _statusText,
                  style: const TextStyle(
                    color: Color(0xFFA9B2C0),
                    fontSize: 10,
                  ),
                ),
              ],
            )
          : Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'G1 · Robot Control Console',
                  style: TextStyle(color: Color(0xFFA9B2C0), fontSize: 10),
                ),
                Text(
                  _statusText,
                  style: const TextStyle(
                    color: Color(0xFFA9B2C0),
                    fontSize: 10,
                  ),
                ),
              ],
            ),
    );
  }

  String get _statusText => controller.isHardware
      ? 'FastAPI → SkillRuntime → Unitree G1'
      : 'FastAPI → SkillRuntime → SimulatedRobotAdapter';
}
