import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../controllers/console_controller.dart';
import '../services/console_api.dart';
import 'console_intents.dart';
import 'widgets/camera_panel.dart';
import 'widgets/model_panel.dart';
import 'widgets/tool_panel.dart';
import 'widgets/skill_panel.dart';
import 'widgets/prompt_panel.dart';
import 'widgets/backend_panel.dart';
import 'widgets/task_input_panel.dart';
import 'widgets/stop_task_button.dart';
import 'widgets/log_panel.dart';
import 'widgets/console_rail.dart';
import 'widgets/console_header.dart';
import 'widgets/console_heading.dart';
import 'widgets/console_footer.dart';

class G1ConsolePage extends StatefulWidget {
  const G1ConsolePage({super.key, this.api});

  final ConsoleApi? api;

  @override
  State<G1ConsolePage> createState() => _G1ConsolePageState();
}

class _G1ConsolePageState extends State<G1ConsolePage> {
  late final ConsoleController controller;

  @override
  void initState() {
    super.initState();
    controller = ConsoleController(onMessage: _toast, api: widget.api)
      ..initialize();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          behavior: SnackBarBehavior.floating,
          width: min(MediaQuery.sizeOf(context).width - 32, 420),
          backgroundColor: const Color(0xFF23344E),
          duration: const Duration(seconds: 2),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, child) => Shortcuts(
        shortcuts: const {
          SingleActivator(LogicalKeyboardKey.enter, control: true):
              SubmitTaskIntent(),
          SingleActivator(LogicalKeyboardKey.enter, meta: true):
              SubmitTaskIntent(),
          SingleActivator(LogicalKeyboardKey.escape): StopTaskIntent(),
        },
        child: Actions(
          actions: {
            SubmitTaskIntent: CallbackAction<SubmitTaskIntent>(
              onInvoke: (_) {
                controller.submitTask();
                return null;
              },
            ),
            StopTaskIntent: CallbackAction<StopTaskIntent>(
              onInvoke: (_) {
                controller.cancelTask();
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: Scaffold(
              body: LayoutBuilder(
                builder: (context, constraints) {
                  final showRail = constraints.maxWidth > 640;
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (showRail)
                        ConsoleRail(
                          width: constraints.maxWidth > 930 ? 88 : 66,
                        ),
                      Expanded(
                        child: _buildApplication(
                          constraints.maxWidth -
                              (showRail
                                  ? (constraints.maxWidth > 930 ? 88 : 66)
                                  : 0),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildApplication(double width) {
    return Column(
      children: [
        ConsoleHeader(controller: controller, width: width),
        Expanded(
          child: SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(
              width <= 640 ? 14 : 32,
              width <= 640 ? 20 : 28,
              width <= 640 ? 14 : 32,
              0,
            ),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1760),
                child: Column(
                  children: [
                    ConsoleHeading(controller: controller, width: width),
                    const SizedBox(height: 24),
                    _buildWorkspace(width),
                    const SizedBox(height: 20),
                    LogPanel(controller: controller, width: width),
                    ConsoleFooter(controller: controller, width: width),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildWorkspace(double width) {
    final twoColumns = width > 930;
    final monitor = Column(
      children: [
        CameraPanel(controller: controller),
        const SizedBox(height: 18),
        _buildExecutionPanels(),
      ],
    );
    final controls = _buildControls(width);
    if (twoColumns) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: monitor),
          const SizedBox(width: 20),
          SizedBox(width: width >= 1500 ? 355 : 322, child: controls),
        ],
      );
    }
    return Column(children: [monitor, const SizedBox(height: 18), controls]);
  }

  Widget _buildExecutionPanels() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final panels = [
          ModelPanel(controller: controller),
          ToolPanel(controller: controller),
          SkillPanel(controller: controller),
        ];
        if (constraints.maxWidth >= 900) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < panels.length; i++) ...[
                Expanded(flex: i == 2 ? 106 : 100, child: panels[i]),
                if (i < panels.length - 1) const SizedBox(width: 15),
              ],
            ],
          );
        }
        if (constraints.maxWidth >= 620) {
          return Column(
            children: [
              Row(
                children: [
                  Expanded(child: panels[0]),
                  const SizedBox(width: 15),
                  Expanded(child: panels[1]),
                ],
              ),
              const SizedBox(height: 15),
              panels[2],
            ],
          );
        }
        return Column(
          children: [
            panels[0],
            const SizedBox(height: 15),
            panels[1],
            const SizedBox(height: 15),
            panels[2],
          ],
        );
      },
    );
  }

  Widget _buildControls(double width) {
    final items = <Widget>[
      PromptPanel(controller: controller),
      BackendPanel(controller: controller),
      TaskInputPanel(controller: controller),
      StopTaskButton(controller: controller),
    ];
    if (width <= 930 && width > 640) {
      return Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: items[0]),
              const SizedBox(width: 16),
              Expanded(child: items[1]),
            ],
          ),
          const SizedBox(height: 16),
          items[2],
          const SizedBox(height: 16),
          items[3],
        ],
      );
    }
    return Column(
      children: [
        items[0],
        const SizedBox(height: 16),
        items[1],
        const SizedBox(height: 16),
        items[2],
        const SizedBox(height: 16),
        items[3],
      ],
    );
  }
}
