class ConsoleLog {
  const ConsoleLog(
    this.time,
    this.level,
    this.source,
    this.message, {
    this.id = '',
  });

  factory ConsoleLog.fromJson(Map<String, dynamic> json) => ConsoleLog(
    json['time'] as String? ?? '',
    json['level'] as String? ?? 'INFO',
    json['source'] as String? ?? 'backend',
    json['message'] as String? ?? '',
    id: json['id'] as String? ?? '',
  );

  final String id;
  final String time;
  final String level;
  final String source;
  final String message;
}
