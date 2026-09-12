import 'dart:async';
import 'dart:math';
import 'dart:typed_data';

import 'camera_grid_painter.dart';
import 'package:flutter/material.dart';

import '../../../../core/theme/console_colors.dart';
import '../../controllers/console_controller.dart';
import '../../services/console_api.dart';
import 'console_widgets.dart';

class CameraPanel extends StatelessWidget {
  const CameraPanel({super.key, required this.controller});

  final ConsoleController controller;

  @override
  Widget build(BuildContext context) {
    final liveCamera =
        controller.cameraSource == 'local' &&
        controller.cameraFrameAvailable &&
        controller.cameraStatus == 'ready';
    return panel(
      header: sectionTitle(Icons.videocam_outlined, '摄像头'),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          tag('RGB'),
          const SizedBox(width: 10),
          Container(
            height: 32,
            padding: const EdgeInsets.symmetric(horizontal: 6),
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFFE3E8F0)),
              borderRadius: BorderRadius.circular(6),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: controller.cameraSource,
                borderRadius: BorderRadius.circular(8),
                style: const TextStyle(color: Color(0xFF64728A), fontSize: 12),
                items: const [
                  DropdownMenuItem(value: 'demo', child: Text('模拟视频源')),
                  DropdownMenuItem(value: 'local', child: Text('本机摄像头')),
                ],
                onChanged: (value) {
                  if (value == null) return;
                  controller.selectCameraSource(value);
                },
              ),
            ),
          ),
        ],
      ),
      child: Column(
        children: [
          LayoutBuilder(
            builder: (context, constraints) {
              final normalHeight = (constraints.maxWidth * 0.47).clamp(
                245.0,
                450.0,
              );
              return AnimatedContainer(
                duration: const Duration(milliseconds: 240),
                height: controller.cameraExpanded
                    ? min(MediaQuery.sizeOf(context).height * .72, 680)
                    : normalHeight,
                margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
                clipBehavior: Clip.antiAlias,
                decoration: BoxDecoration(
                  color: const Color(0xFF101B2C),
                  borderRadius: BorderRadius.circular(7),
                ),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (liveCamera)
                      _LiveCameraFrame(
                        api: controller.api,
                        framePath: controller.cameraFramePath,
                        targetFps: controller.cameraFps,
                      ),
                    if (!liveCamera) CustomPaint(painter: CameraGridPainter()),
                    if (!liveCamera)
                      Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 53,
                              height: 53,
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                color: const Color(
                                  0xFFA1BEFF,
                                ).withValues(alpha: .025),
                                border: Border.all(
                                  color: const Color(
                                    0xFFD0E0FF,
                                  ).withValues(alpha: .14),
                                ),
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Icon(
                                controller.cameraStatus == 'error'
                                    ? Icons.videocam_off_outlined
                                    : Icons.videocam_outlined,
                                size: 27,
                                color: const Color(0xFF8296B5),
                              ),
                            ),
                            const SizedBox(height: 15),
                            Text(
                              controller.cameraStatus == 'error'
                                  ? '视觉通道异常'
                                  : controller.cameraSource == 'local'
                                  ? '等待 D435i 画面'
                                  : '模拟视觉通道就绪',
                              style: const TextStyle(
                                color: Color(0xFFBAC8DF),
                                fontSize: 16,
                                fontWeight: FontWeight.w500,
                                letterSpacing: 1,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 28,
                              ),
                              child: Text(
                                controller.cameraError ??
                                    (controller.cameraSource == 'local'
                                        ? '画面由 FastAPI 后端的 USB RealSense 提供'
                                        : '切换到本机摄像头以启用 D435i'),
                                textAlign: TextAlign.center,
                                style: const TextStyle(
                                  color: Color(0xFF667C9C),
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    Positioned(
                      left: 20,
                      right: 20,
                      top: 18,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          darkChip(
                            controller.cameraSource == 'local'
                                ? 'D435i · ${controller.cameraStatus.toUpperCase()}'
                                : 'SIMULATED FEED',
                          ),
                          darkChip(controller.formattedTime()),
                        ],
                      ),
                    ),
                    Positioned(
                      left: 20,
                      right: 20,
                      bottom: 16,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Flexible(
                            child: darkChip(
                              '${controller.cameraWidth} × ${controller.cameraHeight}'
                              '     ${controller.cameraLabel} · ${controller.cameraFps} FPS',
                            ),
                          ),
                          Row(
                            children: [
                              glassButton(
                                Icons.photo_camera_outlined,
                                liveCamera ? '实时画面' : '等待画面',
                                () => controller.onMessage(
                                  liveCamera
                                      ? '当前显示 D435i 实时画面'
                                      : '当前没有可用的真实画面',
                                ),
                              ),
                              const SizedBox(width: 7),
                              glassButton(
                                controller.cameraExpanded
                                    ? Icons.fullscreen_exit
                                    : Icons.fullscreen,
                                '展开画面',
                                controller.toggleCameraExpanded,
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
          _buildTelemetry(),
        ],
      ),
    );
  }

  Widget _buildTelemetry() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
      child: Row(
        children: [
          _metric(
            '运行状态',
            controller.busy
                ? '执行中'
                : controller.backend
                ? '就绪'
                : '待机',
            dotColor: controller.busy
                ? ConsoleColors.blue
                : controller.backend
                ? ConsoleColors.green
                : const Color(0xFF9FACBD),
          ),
          _metric(
            '机器人连接',
            controller.robotConnected ? '在线' : '离线',
            dotColor: controller.robotConnected
                ? ConsoleColors.green
                : const Color(0xFFD46170),
          ),
          _metric(
            '通信延迟',
            controller.backend ? '${controller.latency} ms' : '— ms',
          ),
          _metric('执行任务', '${controller.taskCount} 次', last: true),
        ],
      ),
    );
  }

  Widget _metric(
    String label,
    String value, {
    Color? dotColor,
    Widget? suffix,
    bool last = false,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          border: last
              ? null
              : const Border(right: BorderSide(color: ConsoleColors.line)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: Color(0xFF9AA3B2), fontSize: 11),
            ),
            const SizedBox(height: 5),
            Row(
              children: [
                if (dotColor != null) ...[
                  dot(dotColor),
                  const SizedBox(width: 7),
                ],
                Flexible(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      value,
                      style: const TextStyle(
                        color: Color(0xFF3B4B63),
                        fontSize: 17,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ),
                if (suffix != null) ...[const SizedBox(width: 8), suffix],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _LiveCameraFrame extends StatefulWidget {
  const _LiveCameraFrame({
    required this.api,
    required this.framePath,
    required this.targetFps,
  });

  final ConsoleApi api;
  final String framePath;
  final int targetFps;

  @override
  State<_LiveCameraFrame> createState() => _LiveCameraFrameState();
}

class _LiveCameraFrameState extends State<_LiveCameraFrame> {
  Uint8List? _frame;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _startFramePump();
  }

  @override
  void didUpdateWidget(covariant _LiveCameraFrame oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.api != widget.api ||
        oldWidget.framePath != widget.framePath ||
        oldWidget.targetFps != widget.targetFps) {
      _startFramePump();
    }
  }

  void _startFramePump() {
    final generation = ++_generation;
    unawaited(_pumpFrames(generation));
  }

  Future<void> _pumpFrames(int generation) async {
    final fps = widget.targetFps.clamp(1, 30);
    final frameInterval = Duration(microseconds: (1000000 / fps).round());
    while (mounted && generation == _generation) {
      final started = DateTime.now();
      try {
        final frame = await widget.api
            .fetchCameraFrame(widget.framePath)
            .timeout(const Duration(seconds: 2));
        if (!mounted || generation != _generation) return;
        if (frame.isNotEmpty) setState(() => _frame = frame);
      } catch (_) {
        if (!mounted || generation != _generation) return;
        await Future<void>.delayed(const Duration(milliseconds: 200));
      }

      final elapsed = DateTime.now().difference(started);
      final remaining = frameInterval - elapsed;
      if (remaining > Duration.zero) await Future<void>.delayed(remaining);
    }
  }

  @override
  void dispose() {
    _generation += 1;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final frame = _frame;
    if (frame == null) {
      return const Center(
        child: SizedBox.square(
          dimension: 24,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: Color(0xFF8296B5),
          ),
        ),
      );
    }
    return RepaintBoundary(
      child: Image.memory(
        frame,
        fit: BoxFit.cover,
        gaplessPlayback: true,
        errorBuilder: (context, error, stackTrace) => const Center(
          child: Icon(
            Icons.broken_image_outlined,
            size: 36,
            color: Color(0xFF8296B5),
          ),
        ),
      ),
    );
  }
}
