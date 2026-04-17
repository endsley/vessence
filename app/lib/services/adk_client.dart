/// HTTP client for the Google ADK server.
///
/// Uses [Dio] for REST calls and the [http] package for SSE streaming
/// (Dio's receiveTimeout kills long-lived streams).
library;

import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:http/http.dart' as http;

import '../models/adk_models.dart';

class AdkClient {
  final Dio _dio;
  final http.Client _httpClient;
  final String baseUrl;
  final String appName;

  AdkClient({
    required this.baseUrl,
    this.appName = 'amber',
    Dio? dio,
    http.Client? httpClient,
  })  : _dio = dio ?? Dio(),
        _httpClient = httpClient ?? http.Client() {
    _dio.options
      ..baseUrl = baseUrl
      ..connectTimeout = const Duration(seconds: 10)
      ..receiveTimeout = const Duration(seconds: 30)
      ..headers = {'Content-Type': 'application/json'};
  }

  // ── Health ──────────────────────────────────────────────────────

  /// Returns true if the ADK server is reachable.
  Future<bool> healthCheck() async {
    try {
      final res = await _dio.get('/health');
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── Session management ──────────────────────────────────────────

  /// Create a new session. Returns the created [AdkSession].
  Future<AdkSession> createSession({
    required String userId,
    String? sessionId,
    Map<String, dynamic>? state,
  }) async {
    final req = CreateSessionRequest(sessionId: sessionId, state: state);
    final res = await _dio.post(
      '/apps/$appName/users/$userId/sessions',
      data: req.toJson(),
    );
    return AdkSession.fromJson(res.data as Map<String, dynamic>);
  }

  /// Fetch an existing session.
  Future<AdkSession> getSession({
    required String userId,
    required String sessionId,
  }) async {
    final res = await _dio.get(
      '/apps/$appName/users/$userId/sessions/$sessionId',
    );
    return AdkSession.fromJson(res.data as Map<String, dynamic>);
  }

  /// Delete a session.
  Future<void> deleteSession({
    required String userId,
    required String sessionId,
  }) async {
    await _dio.delete(
      '/apps/$appName/users/$userId/sessions/$sessionId',
    );
  }

  // ── Run (synchronous) ──────────────────────────────────────────

  /// Send a message and wait for the complete response.
  /// Returns all events from the agent run.
  Future<List<AdkEvent>> run({
    required String userId,
    required String sessionId,
    required String text,
  }) async {
    final req = RunAgentRequest.text(
      appName: appName,
      userId: userId,
      sessionId: sessionId,
      text: text,
    );
    final res = await _dio.post(
      '/run',
      data: req.toJson(),
      options: Options(receiveTimeout: const Duration(minutes: 5)),
    );
    final list = res.data as List<dynamic>;
    return list
        .cast<Map<String, dynamic>>()
        .map(AdkEvent.fromJson)
        .toList();
  }

  // ── Run SSE (streaming) ─────────────────────────────────────────

  /// Send a message and stream back events via SSE.
  ///
  /// Uses the raw [http] package to avoid Dio's receiveTimeout
  /// killing the stream mid-response.
  Stream<AdkEvent> runStream({
    required String userId,
    required String sessionId,
    required String text,
  }) {
    final req = RunAgentRequest.text(
      appName: appName,
      userId: userId,
      sessionId: sessionId,
      text: text,
      streaming: true,
    );

    final controller = StreamController<AdkEvent>();

    () async {
      try {
        final request = http.Request('POST', Uri.parse('$baseUrl/run_sse'))
          ..headers['Content-Type'] = 'application/json'
          ..body = jsonEncode(req.toJson());

        final response = await _httpClient.send(request);

        if (response.statusCode != 200) {
          final body = await response.stream.bytesToString();
          controller.addError(
            AdkException(response.statusCode, 'SSE request failed: $body'),
          );
          await controller.close();
          return;
        }

        await response.stream
            .transform(utf8.decoder)
            .transform(const LineSplitter())
            .forEach((line) {
          if (!line.startsWith('data:')) return;
          final data = line.substring(5).trim();
          if (data.isEmpty) return;

          final json = jsonDecode(data) as Map<String, dynamic>;
          if (json.containsKey('error')) {
            controller.addError(
              AdkException(0, json['error'] as String),
            );
            return;
          }
          controller.add(AdkEvent.fromJson(json));
        });

        await controller.close();
      } catch (e, st) {
        controller.addError(e, st);
        await controller.close();
      }
    }();

    return controller.stream;
  }

  /// Extract the final assistant text from a list of events,
  /// filtering out function call/response events.
  static String extractText(List<AdkEvent> events) {
    return events
        .where((e) => !e.isFunctionCall && !e.isFunctionResponse)
        .map((e) => e.text)
        .where((t) => t.isNotEmpty)
        .join();
  }

  /// Dispose underlying HTTP clients.
  void dispose() {
    _dio.close();
    _httpClient.close();
  }
}

/// Exception thrown when the ADK server returns an error.
class AdkException implements Exception {
  final int statusCode;
  final String message;

  const AdkException(this.statusCode, this.message);

  @override
  String toString() => 'AdkException($statusCode): $message';
}
