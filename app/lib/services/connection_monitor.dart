/// Monitors connectivity to the ADK server via periodic health checks.
library;

import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'adk_client.dart';

/// Connection state exposed to the UI.
enum ServerConnectionState {
  connected,
  disconnected,
  checking,
}

/// Riverpod provider that pings the ADK server every [_pingInterval] and
/// listens to OS-level network changes via connectivity_plus.
final connectionStateProvider =
    StateNotifierProvider<ConnectionMonitor, ServerConnectionState>(
  (ref) => ConnectionMonitor(
    adkClient: AdkClient(baseUrl: 'http://localhost:8000'),
  ),
);

class ConnectionMonitor extends StateNotifier<ServerConnectionState> {
  final AdkClient _client;
  Timer? _pingTimer;
  StreamSubscription<List<ConnectivityResult>>? _connectivitySub;

  static const _pingInterval = Duration(seconds: 15);
  static const _retryInterval = Duration(seconds: 5);

  ConnectionMonitor({required AdkClient adkClient})
      : _client = adkClient,
        super(ServerConnectionState.checking) {
    _start();
  }

  void _start() {
    // Initial check.
    _ping();

    // Schedule periodic pings.
    _pingTimer = Timer.periodic(_pingInterval, (_) => _ping());

    // React to OS-level network changes (WiFi off, etc.).
    _connectivitySub =
        Connectivity().onConnectivityChanged.listen((results) {
      final hasNetwork =
          results.any((r) => r != ConnectivityResult.none);
      if (hasNetwork) {
        // Network came back — check server immediately.
        _ping();
      } else {
        state = ServerConnectionState.disconnected;
      }
    });
  }

  Future<void> _ping() async {
    final ok = await _client.healthCheck();
    if (!mounted) return;
    state = ok
        ? ServerConnectionState.connected
        : ServerConnectionState.disconnected;

    // If disconnected, retry sooner than the normal interval.
    if (!ok) {
      _pingTimer?.cancel();
      _pingTimer = Timer.periodic(_retryInterval, (_) => _ping());
    } else {
      // Restore normal interval if we were in retry mode.
      if (_pingTimer != null && _pingTimer!.tick == 0) return;
      _pingTimer?.cancel();
      _pingTimer = Timer.periodic(_pingInterval, (_) => _ping());
    }
  }

  /// Force an immediate connectivity check (e.g. after user taps retry).
  Future<void> checkNow() async => _ping();

  @override
  void dispose() {
    _pingTimer?.cancel();
    _connectivitySub?.cancel();
    _client.dispose();
    super.dispose();
  }
}
