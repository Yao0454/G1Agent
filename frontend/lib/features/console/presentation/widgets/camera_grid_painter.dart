import 'dart:math';

import 'package:flutter/material.dart';

class CameraGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final background = Paint()
      ..shader =
          RadialGradient(
            colors: const [Color(0xFF1A2A43), Color(0xFF101A2B)],
            stops: const [0, 1],
            radius: .75,
          ).createShader(
            Rect.fromCircle(center: center, radius: size.longestSide * .65),
          );
    canvas.drawRect(Offset.zero & size, background);

    final gridPaint = Paint()
      ..color = const Color(0xFF9AB3DC).withValues(alpha: .04)
      ..strokeWidth = 1;
    const gap = 40.0;
    for (double x = (size.width % gap) / 2; x < size.width; x += gap) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = (size.height % gap) / 2; y < size.height; y += gap) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final guide = Paint()
      ..color = const Color(0xFF92B5EA).withValues(alpha: .13)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    final boxWidth = min(size.width * .62, 480.0);
    final boxHeight = size.height * .66;
    const corner = 20.0;
    final rect = Rect.fromCenter(
      center: center,
      width: boxWidth,
      height: boxHeight,
    );
    final path = Path()
      ..moveTo(rect.left + corner, rect.top)
      ..lineTo(rect.left, rect.top)
      ..lineTo(rect.left, rect.top + corner)
      ..moveTo(rect.right - corner, rect.top)
      ..lineTo(rect.right, rect.top)
      ..lineTo(rect.right, rect.top + corner)
      ..moveTo(rect.left, rect.bottom - corner)
      ..lineTo(rect.left, rect.bottom)
      ..lineTo(rect.left + corner, rect.bottom)
      ..moveTo(rect.right - corner, rect.bottom)
      ..lineTo(rect.right, rect.bottom)
      ..lineTo(rect.right, rect.bottom - corner);
    canvas.drawPath(path, guide);

    final textPainter = TextPainter(
      text: const TextSpan(
        text: 'X  0.00    Y  0.00    Z  0.00',
        style: TextStyle(
          color: Color(0xFF5D779A),
          fontSize: 9,
          fontFamily: 'monospace',
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    textPainter.paint(canvas, Offset(20, size.height - 66));
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
