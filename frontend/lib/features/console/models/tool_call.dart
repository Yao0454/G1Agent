class ToolCall {
  const ToolCall(this.name, this.payload);

  factory ToolCall.fromJson(Map<String, dynamic> json) => ToolCall(
    json['name'] as String? ?? 'unknown',
    json['payload'] as String? ?? '',
  );

  final String name;
  final String payload;
}
