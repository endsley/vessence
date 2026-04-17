/// A slim banner displayed at the top of the chat area when the ADK server
/// is unreachable.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/connection_monitor.dart';

class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connectionState = ref.watch(connectionStateProvider);

    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 300),
      child: connectionState == ServerConnectionState.connected
          ? const SizedBox.shrink()
          : Material(
              key: const ValueKey('offline-banner'),
              color: connectionState == ServerConnectionState.checking
                  ? Colors.orange.shade800
                  : Colors.red.shade800,
              child: InkWell(
                onTap: () =>
                    ref.read(connectionStateProvider.notifier).checkNow(),
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        connectionState == ServerConnectionState.checking
                            ? Icons.sync
                            : Icons.cloud_off,
                        size: 16,
                        color: Colors.white,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        connectionState == ServerConnectionState.checking
                            ? 'Connecting to server...'
                            : 'Server unreachable — tap to retry',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
    );
  }
}
