/// Data models for Google ADK server communication.
library;

/// Request to create a new ADK session.
class CreateSessionRequest {
  final String? sessionId;
  final Map<String, dynamic>? state;

  const CreateSessionRequest({this.sessionId, this.state});

  Map<String, dynamic> toJson() => {
        if (sessionId != null) 'session_id': sessionId,
        if (state != null) 'state': state,
      };
}

/// An ADK session returned by the server.
class AdkSession {
  final String id;
  final String appName;
  final String userId;
  final Map<String, dynamic> state;

  const AdkSession({
    required this.id,
    required this.appName,
    required this.userId,
    this.state = const {},
  });

  factory AdkSession.fromJson(Map<String, dynamic> json) => AdkSession(
        id: json['id'] as String,
        appName: json['app_name'] as String,
        userId: json['user_id'] as String,
        state: (json['state'] as Map<String, dynamic>?) ?? const {},
      );
}

/// Request body for /run and /run_sse endpoints.
class RunAgentRequest {
  final String appName;
  final String userId;
  final String sessionId;
  final Map<String, dynamic>? newMessage;
  final bool streaming;

  const RunAgentRequest({
    required this.appName,
    required this.userId,
    required this.sessionId,
    this.newMessage,
    this.streaming = false,
  });

  /// Build a text-only user message.
  factory RunAgentRequest.text({
    required String appName,
    required String userId,
    required String sessionId,
    required String text,
    bool streaming = false,
  }) =>
      RunAgentRequest(
        appName: appName,
        userId: userId,
        sessionId: sessionId,
        streaming: streaming,
        newMessage: {
          'role': 'user',
          'parts': [
            {'text': text},
          ],
        },
      );

  Map<String, dynamic> toJson() => {
        'app_name': appName,
        'user_id': userId,
        'session_id': sessionId,
        'streaming': streaming,
        if (newMessage != null) 'new_message': newMessage,
      };
}

/// A single event from the ADK agent run.
class AdkEvent {
  final String? eventId;
  final String? author;
  final Map<String, dynamic>? content;
  final Map<String, dynamic> raw;

  const AdkEvent({
    this.eventId,
    this.author,
    this.content,
    required this.raw,
  });

  factory AdkEvent.fromJson(Map<String, dynamic> json) => AdkEvent(
        eventId: json['id'] as String?,
        author: json['author'] as String?,
        content: json['content'] as Map<String, dynamic>?,
        raw: json,
      );

  /// Extract all text parts from the event content.
  String get text {
    final parts = content?['parts'] as List<dynamic>?;
    if (parts == null) return '';
    return parts
        .whereType<Map<String, dynamic>>()
        .where((p) => p.containsKey('text'))
        .map((p) => p['text'] as String)
        .join();
  }

  /// True if this event contains a function call (tool use).
  bool get isFunctionCall {
    final parts = content?['parts'] as List<dynamic>?;
    if (parts == null) return false;
    return parts
        .whereType<Map<String, dynamic>>()
        .any((p) => p.containsKey('functionCall') || p.containsKey('function_call'));
  }

  /// True if this event contains a function response.
  bool get isFunctionResponse {
    final parts = content?['parts'] as List<dynamic>?;
    if (parts == null) return false;
    return parts
        .whereType<Map<String, dynamic>>()
        .any((p) => p.containsKey('functionResponse') || p.containsKey('function_response'));
  }
}
