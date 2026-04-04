# Project Ambient — Cross-Platform Native App
**Priority:** #1 (Primary Development Focus)
**Last Updated:** 2026-03-17 (rev 2 — full testing strategy, Phase 4/5/6 tests, TTS/wake word research added)
**Status:** Spec Phase — Open questions in Section 10 must be answered before coding Phase 1.

---

## 1. Vision

Replace Discord as the primary interface for talking to Amber. Build a native, cross-platform app that looks and feels like ChatGPT — clean, fast, polished — but talks directly to the local Amber ADK server. Discord remains as a secondary notification/remote-trigger channel, not the main UI.

**Target Platforms (in priority order):** Linux desktop → Android → Windows → macOS → iOS (stretch)

---

## 2. Framework: Flutter

Flutter is the only mature framework that compiles true native code on all four targets from one Dart codebase. After research across Flutter, React Native, Tauri v2, and Electron:

| Criterion | Flutter | React Native | Tauri v2 | Electron |
|---|---|---|---|---|
| Linux desktop | ✅ Native | ⚠️ Experimental | ✅ Native | ✅ (Chromium) |
| Android | ✅ Native | ✅ Native | ⚠️ New/unstable | ❌ |
| Single codebase | ✅ | ⚠️ Partial | ✅ | ✅ |
| Performance | ✅ 60/120fps | ⚠️ Bridge overhead | ✅ | ❌ Heavy |
| UI flexibility | ✅ Pixel-perfect | ⚠️ Platform-constrained | ✅ Web CSS | ✅ Web CSS |

**Dart language note:** Close to TypeScript/Java in feel. Strong typing, async/await, no GC pauses at runtime.

---

## 3. Technology Stack & Package Decisions

All packages selected based on research (pub.dev, GitHub activity, Linux desktop compatibility).

### 3.1 Core Dependencies

```yaml
dependencies:
  flutter:
    sdk: flutter

  # ── UI ────────────────────────────────────────────────────────────
  flutter_chat_ui: ^2.x          # Chat message list + bubble framework
  markdown_widget: ^3.x          # Markdown rendering with built-in syntax highlighting
  syntax_highlight: ^0.x         # VSCode-quality code syntax highlighting (TextMate grammars)
  flutter_streaming_text_markdown: ^1.x  # Token-by-token streaming animation
  google_fonts: ^6.x             # JetBrains Mono for code blocks

  # ── Networking ────────────────────────────────────────────────────
  dio: ^5.9.2                    # REST calls (session create, run, health check)
  http: ^1.6.0                   # SSE streaming (http.Client.send() avoids Dio timeout issue)
  retry: ^3.1.2                  # Retry logic for transient network failures
  connectivity_plus: ^7.0.0      # OS-level network state changes

  # ── Persistence ───────────────────────────────────────────────────
  sqflite: ^2.3.3                # SQLite for conversation history
  sqflite_common_ffi: ^2.3.3     # Required for Linux/Windows/macOS desktop
  path: ^1.9.0                   # Path helpers for DB file location
  shared_preferences: ^2.5.4    # Server URL, theme pref, session ID
  flutter_secure_storage: ^10.0.0  # Auth tokens only (requires libsecret on Linux)
  uuid: ^4.5.3                   # Generate conversation IDs, session IDs, user IDs

  # ── State Management ──────────────────────────────────────────────
  flutter_riverpod: ^3.3.1       # Provider-based reactive state

  # ── Voice (Phase 3) ───────────────────────────────────────────────
  record: ^5.x                   # Microphone capture (Linux + Android)
  just_audio: ^0.9.x             # Audio playback for TTS output
  web_socket_channel: ^3.x       # WebSocket to STT server
```

### 3.2 Dev Dependencies

```yaml
dev_dependencies:
  flutter_test:
    sdk: flutter
  integration_test:
    sdk: flutter
  mockito: ^5.6.3                # HTTP client mocking (code-gen)
  mocktail: ^1.0.4               # No-codegen mocks (simpler alternative)
  build_runner: ^2.4.0           # For mockito code generation
  alchemist: ^0.14.0             # Golden/screenshot regression tests
  fake_async: ^1.3.3             # Deterministic timer/stream testing
  sqflite_common_ffi: ^2.3.3     # In-memory DB for unit tests
  http_mock_adapter: ^0.6.1      # Dio HTTP mocking
```

### 3.3 Critical Package Notes

- **`flutter_markdown` is DEPRECATED** (Google, mid-2025). Do not use. The successor `flutter_markdown_plus` requires a custom MarkdownElementBuilder to get syntax highlighting and copy buttons. Use `markdown_widget` instead — it has these built in via `PreConfig.wrapper`.
- **`flutter_highlight` is unmaintained** (last updated 2021). Use `syntax_highlight` for VSCode-quality highlighting.
- **`fetch_client` is web-only** — does not work on Linux desktop. Use `http.Client.send()` for SSE.
- **`flutter_secure_storage` on Linux** requires `libsecret-1-dev` + a running GNOME Keyring / KWallet. In headless environments, use `shared_preferences` instead. Reserve `flutter_secure_storage` for auth tokens only.
- **`dio` and SSE**: Dio's `receiveTimeout` kills streaming connections mid-response. Use the `http` package's raw `send()` for SSE, Dio for all regular REST calls.

---

## 4. UI Design

### 4.1 Layout

```
┌─────────────────────────────────────────────────┐
│ [≡] Sidebar  │        Chat Area                  │
│              │                                   │
│ + New Chat   │  ┌──────────────────────────┐     │
│              │  │  [Amber avatar] Hello!   │     │
│ ─────────── │  └──────────────────────────┘     │
│ Today        │                                   │
│  • Chat 1   │       ┌──────────────────┐        │
│  • Chat 2   │       │ You: What is...  │        │
│             │       └──────────────────┘        │
│ Yesterday   │                                   │
│  • Chat 3   │  ┌──────────────────────────┐     │
│             │  │  [Amber] Here's what...  │     │
│             │  │  ```python               │     │
│             │  │  def foo(): ...          │     │
│             │  │  ```                     │     │
│             │  └──────────────────────────┘     │
│             │                                   │
│             │ ┌─────────────────────────────┐   │
│             │ │ 📎 🎤  Message Amber...  ➤  │   │
│             │ └─────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 4.2 Visual Theme

> **🔬 Research Note (2026-03-26 — auto):**
> # Premium Flutter UI Polish — Technical Note
> 
> ## 1. Animation & Transition Foundation
> 
> ### Page Transitions
> 
> Use **`go_router`** (v14+) with custom transitions — avoid default `MaterialPageRoute` slide:
> 
> ```dart
> GoRoute(
>   path: '/chat',
>   pageBuilder: (context, state) => CustomTransitionPage(
>     child: const ChatScreen(),
>     transitionsBuilder: (context, animation, secondaryAnimation, child) {
>       final curved = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
>       return FadeTransition(
>         opacity: curved,
>         child: SlideTransition(
>           position: Tween<Offset>(begin: const Offset(0, 0.03), end: Offset.zero)
>               .animate(curved),
>           child: child,
>         ),
>       );
>     },
>     transitionDuration: const Duration(milliseconds: 350),
>   ),
> )
> ```
> 
> The key insight: premium apps use **fade + subtle vertical slide** (2-3% of screen height), not full horizontal slides. Claude.ai and Linear both use this pattern.
> 
> ### Message List Animations
> 
> **`flutter_animate`** (v4.5+) is the standard for staggered list entry:
> 
> ```dart
> // Each new message bubble
> MessageBubble(message: msg)
>   .animate()
>   .fadeIn(duration: 200.ms, curve: Curves.easeOut)
>   .slideY(begin: 0.15, end: 0, duration: 250.ms, curve: Curves.easeOutCubic)
>   .scale(begin: const Offset(0.97, 0.97), end: const Offset(1, 1), duration: 200.ms)
> ```
> 
> For staggered entry of multiple messages loading at once:
> 
> ```dart
> ListView.builder(
>   itemBuilder: (ctx, i) => MessageBubble(message: messages[i])
>     .animate(delay: (50 * i).ms) // 50ms stagger per item
>     .fadeIn(duration: 200.ms)
>     .slideY(begin: 0.1, end: 0, duration: 250.ms, curve: Curves.easeOutCubic),
> )
> ```
> 
> ---
> 
> ## 2. Micro-Interactions
> 
> ### Button Press Feedback
> 
> Avoid raw `InkWell`. Use a scale-down press effect (what Linear/Telegram do):
> 
> ```dart
> class PressableScale extends StatefulWidget {
>   final Widget child;
>   final VoidCallback onTap;
>   const PressableScale({required this.child, required this.onTap});
> 
>   @override
>   State<PressableScale> createState() => _PressableScaleState();
> }
> 
> class _PressableScaleState extends State<PressableScale>
>     with SingleTickerProviderStateMixin {
>   late final AnimationController _ctrl = AnimationController(
>     vsync: this,
>     duration: const Duration(milliseconds: 100),
>     reverseDuration: const Duration(milliseconds: 200),
>     upperBound: 1.0,
>   );
> 
>   @override
>   Widget build(BuildContext context) {
>     return GestureDetector(
>       onTapDown: (_) => _ctrl.forward(),
>       onTapUp: (_) { _ctrl.reverse(); widget.onTap(); },
>       onTapCancel: () => _ctrl.reverse(),
>       child: AnimatedBuilder(
>         animation: _ctrl,
>         builder: (_, child) => Transform.scale(
>           scale: 1.0 - (_ctrl.value * 0.04), // scale to 96%
>           child: child,
>         ),
>         child: widget.child,
>       ),
>     );
>   }
> }
> ```
> 
> ### Send Button Animation
> 
> Combine rotation + scale on send:
> 
> ```dart
> IconButton(
>   icon: AnimatedRotation(
>     turns: _isSending ? 0.5 : 0,
>     duration: const Duration(milliseconds: 300),
>     curve: Curves.easeOutBack,
>     child: AnimatedScale(
>       scale: _isSending ? 0.85 : 1.0,
>       duration: const Duration(milliseconds: 150),
>       child: const Icon(Icons.arrow_upward_rounded),
>     ),
>   ),
> )
> ```
> 
> ### Typing Indicator (Three-Dot Bounce)
> 
> No package needed — use staggered `AnimationController`:
> 
> ```dart
> class TypingIndicator extends StatefulWidget { ... }
> 
> class _TypingIndicatorState extends State<TypingIndicator>
>     with TickerProviderStateMixin {
>   late final List<AnimationController> _ctrls = List.generate(3, (i) =>
>     AnimationController(vsync: this, duration: const Duration(milliseconds: 600))
>       ..repeat(reverse: true)
>   );
> 
>   @override
>   void initState() {
>     super.initState();
>     // Stagger start: 0ms, 150ms, 300ms
>     for (var i = 0; i < 3; i++) {
>       Future.delayed(Duration(milliseconds: i * 150), () {
>         if (mounted) _ctrls[i].repeat(reverse: true);
>       });
>     }
>   }
> 
>   @override
>   Widget build(BuildContext context) {
>     return Row(
>       mainAxisSize: MainAxisSize.min,
>       children: List.generate(3, (i) => AnimatedBuilder(
>         animation: _ctrls[i],
>         builder: (_, __) => Container(
>           margin: const EdgeInsets.symmetric(horizontal: 2),
>           child: Transform.translate(
>             offset: Offset(0, -4 * _ctrls[i].value),
>             child: Container(
>               width: 8, height: 8,
>               decoration: BoxDecoration(
>                 color: Colors.white.withValues(alpha: 0.4 + 0.3 * _ctrls[i].value),
>                 shape: BoxShape.circle,
>               ),
>             ),
>           ),
>         ),
>       )),
>     );
>   }
> }
> ```
> 
> ---
> 
> ## 3. Message Bubble Design
> 
> ### What Claude.ai / Linear-tier apps do differently
> 
> | Detail | Implementation |
> |---|---|
> | **No hard border-radius on all corners** | Tail-side corner gets smaller radius (4px vs 18px) |
> | **Grouping** | Consecutive same-sender messages reduce spacing + hide avatar |
> | **Markdown rendering** | Full rich text inside bubbles |
> | **Code blocks** | Syntax-highlighted with copy button, distinct background |
> | **Selection** | Long-press to copy entire message, not just text selection |
> 
> ### Bubble with grouped corners
> 
> ```dart
> BorderRadius _bubbleRadius(bool isUser, bool isFirst, bool isLast) {
>   const r = Radius.circular(18);
>   const tail = Radius.circular(4);
> 
>   if (isUser) {
>     return BorderRadius.only(
>       topLeft: r, topRight: isFirst ? r : tail,
>       bottomLeft: r, bottomRight: isLast ? r : tail,
>     );
>   } else {
>     return BorderRadius.only(
>       topLeft: isFirst ? r : tail, topRight: r,
>       bottomLeft: isLast ? r : tail, bottomRight: r,
>     );
>   }
> }
> ```
> 
> ### Markdown in Bubbles
> 
> **`flutter_markdown`** (v0.7+) with custom theme:
> 
> ```dart
> MarkdownBody(
>   data: message.text,
>   styleSheet: MarkdownStyleSheet(
>     p: const TextStyle(color: Colors.white, fontSize: 15, height: 1.5),
>     code: TextStyle(
>       backgroundColor: Colors.white.withValues(alpha: 0.08),
>       color: const Color(0xFFE8E8E8),
>       fontFamily: 'JetBrains Mono', fontSize: 13,
>     ),
>     codeblockDecoration: BoxDecoration(
>       color: const Color(0xFF1A1A2E),
>       borderRadius: BorderRadius.circular(8),
>     ),
>   ),
> )
> ```
> 
> For syntax highlighting inside code blocks: **`flutter_highlight`** or **`highlight`** (v0.7+).
> 
> ---
> 
> ## 4. Dark Theme Polish
> 
> ### Color System (Claude.ai-inspired)
> 
> ```dart
> class AppColors {
>   // Backgrounds — use subtle warm undertones, not pure gray
>   static const surface0 = Color(0xFF0D0D12);   // deepest bg
>   static const surface1 = Color(0xFF16161E);   // card/panel bg
>   static const surface2 = Color(0xFF1E1E28);   // elevated surface
>   static const surface3 = Color(0xFF2A2A36);   // hover state
> 
>   // Accent
>   static const accent = Color(0xFFD4A574);     // warm amber (Amber-themed)
>   static const accentMuted = Color(0xFF8B7355);
> 
>   // Text
>   static const textPrimary = Color(0xFFECECF1);
>   static const textSecondary = Color(0xFF8E8EA0);
>   static const textTertiary = Color(0xFF56566A);
> 
>   // Bubbles
>   static const userBubble = Color(0xFF2B2B3D);
>   static const assistantBubble = Colors.transparent; // no bg, just text
> }
> ```
> 
> ### Key visual tricks
> 
> 1. **Layered surfaces, not borders** — Use `surface0` → `surface1` → `surface2` to create depth. Avoid visible borders; use 1px box-shadows or elevation instead.
> 
> 2. **Text contrast** — Primary text at 93% white (`0xFFECECF1`), secondary at 56% (`0xFF8E8EA0`). Never pure white.
> 
> 3. **Subtle glow on accent elements**:
> ```dart
> Container(
>   decoration: BoxDecoration(
>     color: AppColors.accent,
>     borderRadius: BorderRadius.circular(20),
>     boxShadow: [
>       BoxShadow(
>         color: AppColors.accent.withValues(alpha: 0.3),
>         blurRadius: 12,
>         spreadRadius: 0,
>       ),
>     ],
>   ),
> )
> ```
> 
> 4. **Input field** — No visible border by default, subtle border on focus:
> ```dart
> InputDecoration(
>   filled: true,
>   fillColor: AppColors.surface2,
>   border: OutlineInputBorder(
>     borderRadius: BorderRadius.circular(12),
>     borderSide: BorderSide.none,
>   ),
>   focusedBorder: OutlineInputBorder(
>     borderRadius: BorderRadius.circular(12),
>     borderSide: BorderSide(color: AppColors.accent.withValues(alpha: 0.4), width: 1),
>   ),
> )
> ```
> 
> ---
> 
> ## 5. Package Summary
> 
> | Package | Version | Purpose |
> |---|---|---|
> | `go_router` | ^14.8 | Routing with custom transitions |
> | `flutter_animate` | ^4.5 | Declarative staggered animations |
> | `flutter_markdown` | ^0.7 | Markdown rendering in bubbles |
> | `flutter_highlight` | ^0.7 | Syntax highlighting in code blocks |
> | `google_fonts` | ^6.2 | Typography (Inter for UI, JetBrains Mono for code) |
> | `shimmer` | ^3.0 | Loading skeleton states |
> | `lottie` | ^3.1 | Complex animations (splash, empty states) |
> 
> **Not recommended**: `animated_text_kit` (janky, not maintained), `flutter_chat_ui` (opinionated, hard to customize to this level).
> 
> ---
> 
> ## 6. Performance Notes
> 
> - Use `RepaintBoundary` around each message bubble — prevents full-list repaints during scroll
> - Use `const` constructors everywhere in bubble widgets
> - For the message list: `CustomScrollView` + `SliverList.builder` with `findChildIndexCallback` for stable keys during insertions
> - Animations should target **only transform and opacity** (GPU-composited layers) — never animate color, padding, or size of complex widgets
> - Test on low-end Android (Pixel 3a tier) — if animations are smooth there, they're smooth everywhere

- Background: `#212121`
- Sidebar: `#171717`
- User bubble: `#2f2f2f`
- Input field: `#2f2f2f`
- Accent: TBD (see Open Question #17)
- Code blocks: `#1E1E1E` (VS Code dark)
- Code block header: `#2D2D2D`
- Font: System default for text; `JetBrains Mono` (via `google_fonts`) for code blocks

### 4.3 Chat Scroll Architecture

Use `CustomScrollView` + `SliverList` (not plain `ListView.builder`) to support sticky date separators:

```dart
CustomScrollView(
  reverse: true,  // newest messages anchor to bottom — CRITICAL
  controller: _scrollController,
  slivers: [
    SliverList(
      delegate: SliverChildBuilderDelegate(
        (context, index) => MessageBubble(messages[index]),
        childCount: messages.length,
        addAutomaticKeepAlives: false,
        addRepaintBoundaries: false,
      ),
    ),
    // Future: SliverPersistentHeader for sticky date headers
  ],
)
```

---

## 5. Backend Connectivity

### 5.1 ADK API Endpoints

The Amber ADK server exposes at `http://{host}:8000`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Server health check / ping |
| `GET` | `/list-apps` | Confirm `amber` app is loaded |
| `POST` | `/apps/amber/users/{user_id}/sessions` | Create a new session |
| `GET` | `/apps/amber/users/{user_id}/sessions/{session_id}` | Verify session exists |
| `DELETE` | `/apps/amber/users/{user_id}/sessions/{session_id}` | Delete session |
| `POST` | `/run` | Send message, receive complete JSON response |
| `POST` | `/run_sse` | Send message, receive SSE token stream |

**Key insight from source code:** ADK already implements `/run_sse` natively as `StreamingResponse` with `media_type="text/event-stream"`. No custom wrapper is needed for Phase 1. The `/run` endpoint returns a complete JSON array of events.

### 5.2 ADK Client Implementation

**`lib/services/adk_client.dart`:**

```dart
class AdkClient {
  final Dio _dio;
  final http.Client _httpClient;

  AdkClient({String baseUrl = 'http://localhost:8000'})
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 90),
          headers: {'Content-Type': 'application/json'},
        )),
        _httpClient = http.Client();

  // Health check
  Future<bool> isHealthy() async {
    try {
      await _dio.get('/health',
          options: Options(sendTimeout: const Duration(seconds: 5),
                           receiveTimeout: const Duration(seconds: 5)));
      return true;
    } catch (_) { return false; }
  }

  // Create session
  Future<String> createSession({required String userId}) async {
    final resp = await _dio.post('/apps/amber/users/$userId/sessions');
    return (resp.data as Map<String, dynamic>)['id'] as String;
  }

  // Verify session still valid
  Future<bool> sessionExists({required String userId, required String sessionId}) async {
    try {
      await _dio.get('/apps/amber/users/$userId/sessions/$sessionId');
      return true;
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return false;
      rethrow;
    }
  }

  // POST /run — blocking, returns full response text
  Future<String> sendMessage({
    required String userId,
    required String sessionId,
    required String text,
  }) async {
    final resp = await _dio.post('/run', data: {
      'app_name': 'amber',
      'user_id': userId,
      'session_id': sessionId,
      'new_message': {'role': 'user', 'parts': [{'text': text}]},
      'streaming': false,
    });
    return _extractText(resp.data as List<dynamic>);
  }

  // POST /run_sse — returns token stream
  Stream<String> sendMessageSse({
    required String userId,
    required String sessionId,
    required String text,
  }) async* {
    final request = http.Request('POST', Uri.parse('${_dio.options.baseUrl}/run_sse'));
    request.headers['Content-Type'] = 'application/json';
    request.headers['Accept'] = 'text/event-stream';
    request.body = jsonEncode({
      'app_name': 'amber',
      'user_id': userId,
      'session_id': sessionId,
      'new_message': {'role': 'user', 'parts': [{'text': text}]},
      'streaming': true,
    });

    final response = await _httpClient.send(request);
    if (response.statusCode != 200) {
      throw Exception('SSE error ${response.statusCode}');
    }

    final parser = SseEventParser();
    await for (final chunk in response.stream.transform(utf8.decoder)) {
      for (final event in parser.feed(chunk)) {
        final parts = (event['content'] as Map?)?['parts'] as List? ?? [];
        for (final part in parts) {
          final t = (part as Map)['text'] as String?;
          if (t != null) yield t;
        }
        if (event['turn_complete'] == true) return;
        if (event['error_code'] != null) {
          throw Exception('ADK error: ${event['error_message']}');
        }
      }
    }
  }

  String _extractText(List<dynamic> events) {
    final buffer = StringBuffer();
    for (final event in events) {
      final parts = (event['content'] as Map?)?['parts'] as List? ?? [];
      for (final part in parts) {
        final t = (part as Map)['text'] as String?;
        if (t != null) buffer.write(t);
      }
    }
    return buffer.toString();
  }

  void dispose() => _httpClient.close();
}
```

### 5.3 SSE Event Parser

```dart
class SseEventParser {
  final StringBuffer _buffer = StringBuffer();

  Iterable<Map<String, dynamic>> feed(String chunk) sync* {
    _buffer.write(chunk);
    while (true) {
      final content = _buffer.toString();
      final sep = content.indexOf('\n\n');
      if (sep == -1) break;
      final block = content.substring(0, sep);
      _buffer.clear();
      _buffer.write(content.substring(sep + 2));
      for (final line in block.split('\n')) {
        if (line.startsWith('data: ')) {
          final json = line.substring(6).trim();
          if (json.isEmpty || json == '[DONE]') continue;
          try { yield jsonDecode(json) as Map<String, dynamic>; } catch (_) {}
        }
      }
    }
  }
}
```

### 5.4 Connection Modes

- **Local:** `http://localhost:8000` — same machine
- **LAN:** `http://192.168.x.x:8000` — same WiFi (Android on home network)
- **Remote:** Tailscale mesh VPN (recommended) — see Open Question #3

### 5.5 Connection Status Management

Poll `GET /health` every 30 seconds. React to OS connectivity events via `connectivity_plus` (but always do an actual HTTP ping — `connectivity_plus` on Linux only checks if an interface is up, not if the server is reachable):

```dart
class AdkConnectionManager {
  final AdkClient _client;
  final _statusController = StreamController<bool>.broadcast();
  Timer? _pingTimer;
  bool _isOnline = false;

  Stream<bool> get statusStream => _statusController.stream;
  bool get isOnline => _isOnline;

  void start() {
    _ping();
    _pingTimer = Timer.periodic(const Duration(seconds: 30), (_) => _ping());
    Connectivity().onConnectivityChanged.listen((results) {
      if (results.contains(ConnectivityResult.none)) {
        _setStatus(false);
      } else {
        _ping();
      }
    });
  }

  Future<void> _ping() async {
    final alive = await _client.isHealthy();
    _setStatus(alive);
  }

  void _setStatus(bool alive) {
    if (_isOnline != alive) {
      _isOnline = alive;
      _statusController.add(alive);
    }
  }

  void dispose() { _pingTimer?.cancel(); _statusController.close(); }
}
```

---

## 6. Database Schema

### 6.1 SQLite Tables

```sql
CREATE TABLE conversations (
  id          TEXT PRIMARY KEY,     -- UUID v4
  title       TEXT NOT NULL,        -- auto-generated from first user message
  created_at  INTEGER NOT NULL,     -- Unix milliseconds
  updated_at  INTEGER NOT NULL,     -- updated on each new message
  session_id  TEXT,                 -- ADK session ID for this conversation
  metadata    TEXT                  -- JSON blob for future fields
);

CREATE TABLE messages (
  id              TEXT PRIMARY KEY, -- UUID v4
  conversation_id TEXT NOT NULL,
  role            TEXT NOT NULL,    -- 'user' | 'assistant' | 'system'
  content         TEXT NOT NULL,
  timestamp       INTEGER NOT NULL, -- Unix milliseconds
  token_count     INTEGER,
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_conv_ts ON messages (conversation_id, timestamp DESC);
CREATE INDEX idx_convs_updated ON conversations (updated_at DESC);
```

### 6.2 Initialization (Platform-Aware)

```dart
Future<Database> openDatabase() async {
  if (Platform.isLinux || Platform.isWindows || Platform.isMacOS) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }
  final path = join(await getDatabasesPath(), 'ambient_chat.db');
  return sqflite.openDatabase(path, version: 1,
    onCreate: (db, v) async {
      final batch = db.batch();
      batch.execute(createConversationsTable);
      batch.execute(createMessagesTable);
      batch.execute(createMessagesIndex);
      batch.execute(createConversationsIndex);
      await batch.commit(noResult: true);
    },
    onUpgrade: (db, old, newV) async {
      if (old < 2) { /* future: add columns here */ }
    },
  );
}
```

### 6.3 Pagination Pattern

```dart
// Load most recent N messages (newest first from DB, reversed for display)
Future<List<Message>> loadLatest(String conversationId, {int limit = 30}) async {
  final rows = await _db.query('messages',
    where: 'conversation_id = ?', whereArgs: [conversationId],
    orderBy: 'timestamp DESC', limit: limit);
  return rows.reversed.map(Message.fromMap).toList();
}

// Load older messages when user scrolls to top
Future<List<Message>> loadOlder(String conversationId, int olderThanMs) async {
  final rows = await _db.query('messages',
    where: 'conversation_id = ? AND timestamp < ?',
    whereArgs: [conversationId, olderThanMs],
    orderBy: 'timestamp DESC', limit: 30);
  return rows.reversed.map(Message.fromMap).toList();
}
```

---

## 7. Session Management

```dart
class SessionManager {
  final SharedPreferences _prefs;
  final AdkClient _client;

  String get userId {
    return _prefs.getString('user_id') ?? _createUserId();
  }

  String _createUserId() {
    final id = const Uuid().v4();
    _prefs.setString('user_id', id);
    return id;
  }

  Future<String> getOrCreateSession(String conversationId) async {
    final key = 'session_$conversationId';
    final existing = _prefs.getString(key);
    if (existing != null) {
      final valid = await _client.sessionExists(userId: userId, sessionId: existing);
      if (valid) return existing;
    }
    final newId = await _client.createSession(userId: userId);
    await _prefs.setString(key, newId);
    return newId;
  }
}
```

---

## 8. Phases — Implementation + Testing

### Pre-Development Checklist

- [ ] Flutter SDK installed (`flutter doctor` reports no critical issues)
- [ ] `flutter config --enable-linux-desktop` run
- [ ] All open questions in Section 10 answered
- [ ] TTS engine selected and tested (XTTS v2 vs F5-TTS)

---

### Phase 1 — Core Chat (MVP)

> **🔬 Research Note (2026-03-26 — auto):**
> # Chat Persistence with sqflite — Technical Note
> 
> ## Package
> 
> **`sqflite_common_ffi: ^2.3.4`** — use this instead of bare `sqflite`. It provides FFI-based SQLite on Linux/Windows/macOS desktops where the native Android `sqflite` plugin doesn't exist. On Android it works identically.
> 
> ```yaml
> dependencies:
>   sqflite_common_ffi: ^2.3.4
>   path_provider: ^2.1.5
>   path: ^1.9.1
> ```
> 
> Initialize once at startup:
> 
> ```dart
> import 'package:sqflite_common_ffi/sqflite_ffi.dart';
> 
> void main() {
>   databaseFactory = databaseFactoryFfi; // works on all platforms
>   runApp(const AmbientApp());
> }
> ```
> 
> ---
> 
> ## Schema
> 
> Two tables: `conversations` (threads) and `messages` (individual turns).
> 
> ```sql
> -- v1
> CREATE TABLE conversations (
>   id         TEXT PRIMARY KEY,           -- UUID
>   title      TEXT NOT NULL DEFAULT '',
>   created_at INTEGER NOT NULL,           -- Unix ms
>   updated_at INTEGER NOT NULL            -- Unix ms, bumped on new message
> );
> 
> CREATE TABLE messages (
>   id              TEXT PRIMARY KEY,      -- UUID
>   conversation_id TEXT NOT NULL,
>   role            TEXT NOT NULL,         -- 'user' | 'assistant' | 'system'
>   content         TEXT NOT NULL,
>   created_at      INTEGER NOT NULL,      -- Unix ms
>   metadata        TEXT,                  -- nullable JSON blob (model, tokens, attachments)
>   FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
> );
> 
> -- Pagination index: newest-first within a conversation
> CREATE INDEX idx_messages_conv_time
>   ON messages(conversation_id, created_at DESC);
> 
> -- Conversation list sorted by recent activity
> CREATE INDEX idx_conversations_updated
>   ON conversations(updated_at DESC);
> ```
> 
> **Why UUIDs instead of autoincrement:** Messages may originate from the server (Amber) with their own IDs, and UUIDs avoid conflicts if you ever sync across devices.
> 
> **Why Unix ms integers instead of ISO strings:** Integer comparison is ~3x faster for range queries and sorting, and sqflite doesn't have a native datetime type anyway.
> 
> ---
> 
> ## Database Helper
> 
> ```dart
> class ChatDatabase {
>   static const _dbName = 'ambient_chat.db';
>   static const _dbVersion = 1;
> 
>   Database? _db;
> 
>   Future<Database> get db async {
>     return _db ??= await _open();
>   }
> 
>   Future<Database> _open() async {
>     final dir = await getApplicationSupportDirectory();
>     final path = join(dir.path, _dbName);
>     return openDatabase(
>       path,
>       version: _dbVersion,
>       onCreate: _onCreate,
>       onUpgrade: _onUpgrade,
>       onConfigure: (db) => db.execute('PRAGMA foreign_keys = ON'),
>     );
>   }
> 
>   Future<void> _onCreate(Database db, int version) async {
>     final batch = db.batch();
>     batch.execute('''
>       CREATE TABLE conversations (
>         id TEXT PRIMARY KEY,
>         title TEXT NOT NULL DEFAULT '',
>         created_at INTEGER NOT NULL,
>         updated_at INTEGER NOT NULL
>       )
>     ''');
>     batch.execute('''
>       CREATE TABLE messages (
>         id TEXT PRIMARY KEY,
>         conversation_id TEXT NOT NULL,
>         role TEXT NOT NULL,
>         content TEXT NOT NULL,
>         created_at INTEGER NOT NULL,
>         metadata TEXT,
>         FOREIGN KEY (conversation_id)
>           REFERENCES conversations(id) ON DELETE CASCADE
>       )
>     ''');
>     batch.execute('''
>       CREATE INDEX idx_messages_conv_time
>         ON messages(conversation_id, created_at DESC)
>     ''');
>     batch.execute('''
>       CREATE INDEX idx_conversations_updated
>         ON conversations(updated_at DESC)
>     ''');
>     await batch.commit(noResult: true);
>   }
> 
>   Future<void> _onUpgrade(Database db, int oldV, int newV) async {
>     // Sequential migration — see section below
>     for (var v = oldV; v < newV; v++) {
>       switch (v) {
>         case 1:
>           await _migrateV1toV2(db);
>         // case 2: await _migrateV2toV3(db);
>       }
>     }
>   }
> }
> ```
> 
> ---
> 
> ## Migrations
> 
> sqflite's `onUpgrade` gives you `(oldVersion, newVersion)`. The pattern above runs each step sequentially so you can go from v1 → v4 on an old install.
> 
> Example future migration:
> 
> ```dart
> Future<void> _migrateV1toV2(Database db) async {
>   // Add a "pinned" flag to conversations
>   await db.execute(
>     'ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0',
>   );
> }
> ```
> 
> **Rules:**
> 1. Never modify an existing migration — only append new ones.
> 2. Wrap multi-statement migrations in `db.transaction()`.
> 3. Bump `_dbVersion` by exactly 1 per release that touches the schema.
> 
> ---
> 
> ## Efficient Pagination (Keyset / Cursor-Based)
> 
> **Do not use OFFSET/LIMIT for chat.** It gets slower as offset grows. Use **keyset pagination** on the `created_at` index instead:
> 
> ```dart
> /// Returns [pageSize] messages older than [beforeTimestamp].
> /// Pass `null` on first load to get the newest messages.
> Future<List<Message>> loadMessages(
>   String conversationId, {
>   int? beforeTimestamp,
>   int pageSize = 40,
> }) async {
>   final d = await db;
>   final where = beforeTimestamp != null
>       ? 'conversation_id = ? AND created_at < ?'
>       : 'conversation_id = ?';
>   final args = beforeTimestamp != null
>       ? [conversationId, beforeTimestamp]
>       : [conversationId];
> 
>   final rows = await d.query(
>     'messages',
>     where: where,
>     whereArgs: args,
>     orderBy: 'created_at DESC',
>     limit: pageSize,
>   );
>   return rows.map(Message.fromRow).toList();
> }
> ```
> 
> **Why this works well:**
> - The compound index `(conversation_id, created_at DESC)` makes this a single index range scan regardless of how deep into history you go.
> - The UI calls `loadMessages(convId, beforeTimestamp: oldestLoadedMsg.createdAt)` when the user scrolls up — constant time per page.
> 
> For the conversation list, same pattern on `updated_at`:
> 
> ```dart
> Future<List<Conversation>> loadConversations({
>   int? beforeUpdatedAt,
>   int pageSize = 20,
> }) async {
>   final d = await db;
>   final rows = await d.query(
>     'conversations',
>     where: beforeUpdatedAt != null ? 'updated_at < ?' : null,
>     whereArgs: beforeUpdatedAt != null ? [beforeUpdatedAt] : null,
>     orderBy: 'updated_at DESC',
>     limit: pageSize,
>   );
>   return rows.map(Conversation.fromRow).toList();
> }
> ```
> 
> ---
> 
> ## Key Recommendations
> 
> | Decision | Recommendation | Rationale |
> |---|---|---|
> | Package | `sqflite_common_ffi` | Single package, all 4 platforms |
> | IDs | UUID v4 (`package:uuid`) | Server-safe, no autoincrement conflicts |
> | Timestamps | `int` Unix ms | Fast sorting, no parsing overhead |
> | Pagination | Keyset on `created_at` | O(1) per page vs O(n) for OFFSET |
> | Foreign keys | `PRAGMA foreign_keys = ON` | Must be set per connection, not per DB |
> | Page size | 40 messages | Enough to fill ~2 screens, small enough to decode fast |
> | Metadata | JSON `TEXT` column | Flexible for model name, token counts, attachments without schema churn |

**Goal:** Working app on Linux + Android. Send messages to Amber, see responses, history persisted locally.

---

#### Task 1.1: Flutter Project Scaffold

**Implementation:**
```bash
flutter create --platforms=linux,android \
  --org com.projectambient \
  --project-name ambient_app \
  ambient_app
cd ambient_app
```

Directory structure:
```
lib/
  main.dart               ← Entry point, app bootstrap
  app.dart                ← MaterialApp + theme + providers
  services/
    adk_client.dart       ← HTTP client (Section 5.2)
    session_manager.dart  ← Session persistence (Section 7)
    connection_manager.dart
    database.dart         ← sqflite setup (Section 6.2)
    message_repository.dart
    conversation_repository.dart
  models/
    message.dart
    conversation.dart
  screens/
    chat_screen.dart
    settings_screen.dart
  widgets/
    chat_bubble.dart
    sidebar.dart
    input_bar.dart
    connection_banner.dart
  state/
    chat_notifier.dart    ← Riverpod StateNotifier for chat state
    conversation_notifier.dart
```

Add all dependencies from Section 3.1 to `pubspec.yaml`.

Linux system deps (one-time on dev machine):
```bash
sudo apt-get install -y ninja-build libgtk-3-dev libx11-dev \
  pkg-config cmake clang libsqlite3-dev
```

**Tests:**
```bash
# Verify both targets build without errors
flutter build linux --debug
flutter build apk --debug
```
Expected: Both exit 0, artifacts produced at `build/linux/x64/debug/bundle/` and `build/app/outputs/flutter-apk/app-debug.apk`.

---

#### Task 1.2: ADK HTTP Client

**Implementation:** `lib/services/adk_client.dart` — full implementation in Section 5.2.

**Unit Tests (`test/services/adk_client_test.dart`):**

```dart
@GenerateMocks([http.Client, Dio])
void main() {
  group('AdkClient', () {
    late MockClient mockHttp;
    late AdkClient client;

    setUp(() { /* inject mocks */ });

    test('isHealthy returns true on 200', () async {
      when(mockDio.get('/health', options: any))
          .thenAnswer((_) async => Response(data: {}, statusCode: 200, requestOptions: RequestOptions()));
      expect(await client.isHealthy(), isTrue);
    });

    test('isHealthy returns false on connection error', () async {
      when(mockDio.get('/health', options: any))
          .thenThrow(DioException(requestOptions: RequestOptions(),
              type: DioExceptionType.connectionError));
      expect(await client.isHealthy(), isFalse);
    });

    test('sendMessage extracts text from event list', () async {
      when(mockDio.post('/run', data: anyNamed('data')))
          .thenAnswer((_) async => Response(
            data: [{'content': {'parts': [{'text': 'Hello!'}]}}],
            statusCode: 200, requestOptions: RequestOptions()));
      expect(await client.sendMessage(userId: 'u', sessionId: 's', text: 'hi'),
             equals('Hello!'));
    });

    test('sendMessage throws on 500', () async {
      when(mockDio.post('/run', data: anyNamed('data')))
          .thenThrow(DioException(requestOptions: RequestOptions(),
              response: Response(statusCode: 500, requestOptions: RequestOptions()),
              type: DioExceptionType.badResponse));
      expect(() => client.sendMessage(userId: 'u', sessionId: 's', text: 'hi'),
             throwsA(isA<DioException>()));
    });

    test('SseEventParser handles chunked delivery', () {
      final parser = SseEventParser();
      final events = <Map<String, dynamic>>[];
      // Simulate TCP splitting an event across two reads
      events.addAll(parser.feed('data: {"turn_'));
      events.addAll(parser.feed('complete":true}\n\n'));
      expect(events.length, equals(1));
      expect(events.first['turn_complete'], isTrue);
    });
  });
}
```

Run: `flutter test test/services/adk_client_test.dart`

---

#### Task 1.3: Chat Bubble UI

**Implementation (`lib/widgets/chat_bubble.dart`):**

```dart
class ChatBubble extends StatelessWidget {
  final String content;
  final String role; // 'user' | 'assistant'
  final bool isStreaming;

  @override
  Widget build(BuildContext context) {
    final isUser = role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isUser ? const Color(0xFF2f2f2f) : const Color(0xFF1e1e1e),
          borderRadius: BorderRadius.circular(12),
        ),
        child: isUser
            ? SelectableText(content, style: const TextStyle(color: Colors.white))
            : MarkdownWidget(
                data: isStreaming ? '$content▋' : content,
                config: MarkdownConfig(configs: [
                  PreConfig(
                    theme: vscodeDarkTheme,
                    textStyle: GoogleFonts.jetBrainsMono(fontSize: 13),
                    wrapper: _codeBlockWrapper,
                  ),
                ]),
              ),
      ),
    );
  }

  Widget _codeBlockWrapper(Widget child, String code, String language) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Container(
        color: const Color(0xFF2D2D2D),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(language, style: const TextStyle(color: Colors.grey, fontSize: 12)),
            IconButton(
              key: const Key('copy_code_button'),
              icon: const Icon(Icons.copy, size: 16, color: Colors.grey),
              onPressed: () => Clipboard.setData(ClipboardData(text: code)),
            ),
          ],
        ),
      ),
      child,
    ],
  );
}
```

**Widget Tests (`test/widgets/chat_bubble_test.dart`):**

```dart
void main() {
  group('ChatBubble', () {
    testWidgets('user bubble is right-aligned', (tester) async {
      await tester.pumpWidget(MaterialApp(home: Scaffold(
        body: ChatBubble(content: 'Hello', role: 'user', isStreaming: false),
      )));
      final align = tester.widget<Align>(find.byType(Align).first);
      expect(align.alignment, equals(Alignment.centerRight));
    });

    testWidgets('assistant bubble is left-aligned', (tester) async {
      await tester.pumpWidget(MaterialApp(home: Scaffold(
        body: ChatBubble(content: 'Hi', role: 'assistant', isStreaming: false),
      )));
      final align = tester.widget<Align>(find.byType(Align).first);
      expect(align.alignment, equals(Alignment.centerLeft));
    });

    testWidgets('code block shows copy button', (tester) async {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: ChatBubble(
        content: '```python\nprint("hi")\n```',
        role: 'assistant',
        isStreaming: false,
      ))));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('copy_code_button')), findsOneWidget);
    });

    testWidgets('streaming shows cursor character', (tester) async {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: ChatBubble(
        content: 'Thinking',
        role: 'assistant',
        isStreaming: true,
      ))));
      await tester.pumpAndSettle();
      expect(find.textContaining('▋'), findsOneWidget);
    });

    testWidgets('user bubble uses SelectableText not MarkdownWidget', (tester) async {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: ChatBubble(
        content: 'Plain text',
        role: 'user',
        isStreaming: false,
      ))));
      expect(find.byType(SelectableText), findsOneWidget);
      expect(find.byType(MarkdownWidget), findsNothing);
    });
  });
}
```

**Golden Test (`test/golden/chat_bubble_golden_test.dart`):**

```dart
void main() {
  goldenTest(
    'ChatBubble states',
    fileName: 'chat_bubble',
    builder: () => GoldenTestGroup(children: [
      GoldenTestScenario(name: 'user message',
        child: ChatBubble(content: 'Hello!', role: 'user', isStreaming: false)),
      GoldenTestScenario(name: 'assistant markdown',
        child: ChatBubble(content: '**Bold** and `inline code`', role: 'assistant', isStreaming: false)),
      GoldenTestScenario(name: 'code block',
        child: SizedBox(width: 350, child: ChatBubble(
          content: '```dart\nvoid main() => runApp(App());\n```',
          role: 'assistant', isStreaming: false))),
      GoldenTestScenario(name: 'streaming',
        child: ChatBubble(content: 'Generating', role: 'assistant', isStreaming: true)),
    ]),
  );
}
```

Generate goldens (run once on Linux): `flutter test --update-goldens test/golden/`
Verify in CI: `flutter test test/golden/`

---

#### Task 1.4: Input Bar

**Implementation (`lib/widgets/input_bar.dart`):**

Multi-line TextField that expands to 4 lines max. Send on Enter (desktop) or button tap. Attachment button (Phase 2). Mic button (Phase 3, disabled initially).

```dart
class InputBar extends StatefulWidget {
  final void Function(String) onSend;
  final bool enabled;

  @override
  State<InputBar> createState() => _InputBarState();
}

class _InputBarState extends State<InputBar> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      color: const Color(0xFF212121),
      child: Row(children: [
        IconButton(icon: const Icon(Icons.attach_file, color: Colors.grey),
          onPressed: null), // Phase 2
        Expanded(child: TextField(
          key: const Key('chat_input'),
          controller: _controller,
          maxLines: 4,
          minLines: 1,
          decoration: InputDecoration(
            hintText: 'Message Amber...',
            hintStyle: const TextStyle(color: Colors.grey),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            filled: true,
            fillColor: const Color(0xFF2f2f2f),
          ),
          onChanged: (v) => setState(() => _hasText = v.trim().isNotEmpty),
          onSubmitted: _submit,
        )),
        IconButton(
          key: const Key('send_button'),
          icon: const Icon(Icons.send),
          color: _hasText && widget.enabled ? Colors.white : Colors.grey,
          onPressed: _hasText && widget.enabled ? () => _submit(_controller.text) : null,
        ),
      ]),
    );
  }

  void _submit(String text) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    widget.onSend(trimmed);
    _controller.clear();
    setState(() => _hasText = false);
  }
}
```

**Widget Tests:**
```dart
testWidgets('send button disabled when input is empty', (tester) async {
  await tester.pumpWidget(MaterialApp(home: Scaffold(
    body: InputBar(onSend: (_) {}, enabled: true),
  )));
  final sendBtn = tester.widget<IconButton>(find.byKey(const Key('send_button')));
  expect(sendBtn.onPressed, isNull);
});

testWidgets('send button enabled when text entered', (tester) async {
  await tester.pumpWidget(MaterialApp(home: Scaffold(
    body: InputBar(onSend: (_) {}, enabled: true),
  )));
  await tester.enterText(find.byKey(const Key('chat_input')), 'Hello');
  await tester.pump();
  final sendBtn = tester.widget<IconButton>(find.byKey(const Key('send_button')));
  expect(sendBtn.onPressed, isNotNull);
});

testWidgets('onSend called with trimmed text, input cleared', (tester) async {
  String? sent;
  await tester.pumpWidget(MaterialApp(home: Scaffold(
    body: InputBar(onSend: (t) => sent = t, enabled: true),
  )));
  await tester.enterText(find.byKey(const Key('chat_input')), '  Hello world  ');
  await tester.tap(find.byKey(const Key('send_button')));
  await tester.pump();
  expect(sent, equals('Hello world'));
  expect(find.text(''), findsOneWidget); // input cleared
});
```

---

#### Task 1.5: Sidebar (Conversation List)

**Implementation:**

Use `AnimatedContainer` to slide sidebar open/closed. Conversations grouped by Today / Yesterday / Previous 7 Days / Older using `updated_at` timestamps.

```dart
class Sidebar extends StatelessWidget {
  final List<Conversation> conversations;
  final String? activeConversationId;
  final VoidCallback onNewChat;
  final void Function(String) onSelectConversation;
  final void Function(String) onDeleteConversation;

  @override
  Widget build(BuildContext context) {
    final grouped = _groupByDate(conversations);
    return Container(
      width: 260,
      color: const Color(0xFF171717),
      child: Column(children: [
        _NewChatButton(onTap: onNewChat),
        Expanded(child: ListView(children: [
          for (final entry in grouped.entries) ...[
            _DateHeader(label: entry.key),
            for (final conv in entry.value)
              _ConversationTile(
                conv: conv,
                isActive: conv.id == activeConversationId,
                onTap: () => onSelectConversation(conv.id),
                onDelete: () => onDeleteConversation(conv.id),
              ),
          ],
        ])),
      ]),
    );
  }

  Map<String, List<Conversation>> _groupByDate(List<Conversation> convs) {
    final now = DateTime.now();
    final result = <String, List<Conversation>>{};
    for (final c in convs) {
      final dt = DateTime.fromMillisecondsSinceEpoch(c.updatedAt);
      final diff = now.difference(dt).inDays;
      final label = diff == 0 ? 'Today'
          : diff == 1 ? 'Yesterday'
          : diff <= 7 ? 'Previous 7 Days'
          : 'Older';
      result.putIfAbsent(label, () => []).add(c);
    }
    return result;
  }
}
```

**Widget Tests:**
```dart
testWidgets('conversations grouped into Today/Yesterday sections', (tester) async {
  final now = DateTime.now().millisecondsSinceEpoch;
  final yesterday = now - const Duration(hours: 25).inMilliseconds;
  final convs = [
    Conversation(id: '1', title: 'Chat A', updatedAt: now, createdAt: now),
    Conversation(id: '2', title: 'Chat B', updatedAt: yesterday, createdAt: yesterday),
  ];
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: Sidebar(
    conversations: convs, activeConversationId: null,
    onNewChat: () {}, onSelectConversation: (_) {}, onDeleteConversation: (_) {},
  ))));
  expect(find.text('Today'), findsOneWidget);
  expect(find.text('Yesterday'), findsOneWidget);
  expect(find.text('Chat A'), findsOneWidget);
  expect(find.text('Chat B'), findsOneWidget);
});

testWidgets('new chat button calls onNewChat', (tester) async {
  bool called = false;
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: Sidebar(
    conversations: [],
    activeConversationId: null,
    onNewChat: () => called = true,
    onSelectConversation: (_) {},
    onDeleteConversation: (_) {},
  ))));
  await tester.tap(find.text('New Chat'));
  expect(called, isTrue);
});
```

---

#### Task 1.6: Local SQLite Persistence

**Unit Tests (`test/services/database_test.dart`):**

```dart
void main() {
  late Database db;

  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  setUp(() async {
    db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath,
      options: OpenDatabaseOptions(version: 1, onCreate: createSchema));
  });

  tearDown(() async => db.close());

  test('insert and retrieve message preserves all fields', () async {
    final repo = MessageRepository(db);
    await repo.insert(Message(id: 'm1', conversationId: 'c1',
        role: 'user', content: 'Hello', timestamp: 1000));
    final msgs = await repo.loadLatest('c1');
    expect(msgs.length, 1);
    expect(msgs.first.content, equals('Hello'));
    expect(msgs.first.role, equals('user'));
  });

  test('loadLatest returns messages in chronological order', () async {
    final repo = MessageRepository(db);
    await repo.insert(Message(id: '2', conversationId: 'c1', role: 'user', content: 'B', timestamp: 2000));
    await repo.insert(Message(id: '1', conversationId: 'c1', role: 'user', content: 'A', timestamp: 1000));
    final msgs = await repo.loadLatest('c1');
    expect(msgs.first.content, equals('A')); // oldest first
    expect(msgs.last.content, equals('B'));
  });

  test('loadOlder returns messages before given timestamp', () async {
    final repo = MessageRepository(db);
    for (int i = 1; i <= 5; i++) {
      await repo.insert(Message(id: '$i', conversationId: 'c1',
          role: 'user', content: 'msg$i', timestamp: i * 1000));
    }
    final older = await repo.loadOlder('c1', 3000); // older than msg3
    expect(older.map((m) => m.content).toList(), equals(['msg1', 'msg2']));
  });

  test('deleting conversation cascades to messages', () async {
    final convRepo = ConversationRepository(db);
    final msgRepo = MessageRepository(db);
    await convRepo.insert(Conversation(id: 'c1', title: 'Test',
        createdAt: 0, updatedAt: 0));
    await msgRepo.insert(Message(id: 'm1', conversationId: 'c1',
        role: 'user', content: 'Hi', timestamp: 0));
    await convRepo.delete('c1');
    final msgs = await msgRepo.loadLatest('c1');
    expect(msgs, isEmpty);
  });

  test('migration v1→v2 adds token_count column', () async {
    // Simulate upgrading
    final db2 = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath,
      options: OpenDatabaseOptions(
        version: 2,
        onCreate: createSchema,
        onUpgrade: migrateSchema,
      ));
    // Should not throw — column exists
    await db2.execute('UPDATE messages SET token_count = 0 WHERE 1=0');
    await db2.close();
  });
}
```

---

#### Task 1.7: Connection Status Indicator

**Implementation:** A `ConnectionBanner` widget that reads from `AdkConnectionManager.statusStream` via Riverpod. Shows a red banner when offline, green indicator dot in the app bar when online.

**Widget Tests:**
```dart
testWidgets('shows red banner when offline', (tester) async {
  final controller = StreamController<bool>();
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: ConnectionBanner(
    statusStream: controller.stream,
    initialStatus: false,
    child: const Text('Content'),
  ))));
  expect(find.text('Amber is offline — retrying...'), findsOneWidget);
  expect(find.byType(Container), matchesColor(Colors.red[800]));
});

testWidgets('hides banner when online', (tester) async {
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: ConnectionBanner(
    statusStream: const Stream.empty(),
    initialStatus: true,
    child: const Text('Content'),
  ))));
  expect(find.text('Amber is offline'), findsNothing);
});

testWidgets('transitions from offline to online removes banner', (tester) async {
  final controller = StreamController<bool>();
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: ConnectionBanner(
    statusStream: controller.stream,
    initialStatus: false,
    child: const Text('Content'),
  ))));
  expect(find.textContaining('offline'), findsOneWidget);
  controller.add(true);
  await tester.pump();
  expect(find.textContaining('offline'), findsNothing);
});
```

---

#### Task 1.8: Settings Screen

**Implementation:** Simple settings screen with server URL field, display name, theme toggle (Phase 2). Persisted via `SharedPreferences`.

**Widget Tests:**
```dart
testWidgets('saves server URL when changed', (tester) async {
  SharedPreferences.setMockInitialValues({'server_url': 'http://localhost:8000'});
  await tester.pumpWidget(MaterialApp(home: SettingsScreen()));
  await tester.enterText(find.byKey(const Key('server_url_field')), 'http://192.168.1.5:8000');
  await tester.tap(find.byKey(const Key('save_settings_button')));
  await tester.pumpAndSettle();
  final prefs = await SharedPreferences.getInstance();
  expect(prefs.getString('server_url'), equals('http://192.168.1.5:8000'));
});
```

---

#### Task 1.9: Dark Theme

**Implementation (`lib/app.dart`):**
```dart
ThemeData get darkTheme => ThemeData(
  brightness: Brightness.dark,
  scaffoldBackgroundColor: const Color(0xFF212121),
  colorScheme: const ColorScheme.dark(
    surface: Color(0xFF171717),
    primary: Color(0xFF10A37F), // GPT green (or Amber accent TBD)
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: const Color(0xFF2f2f2f),
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none),
  ),
  textTheme: const TextTheme(bodyMedium: TextStyle(color: Colors.white)),
);
```

**Golden Test:**
```dart
goldenTest('App dark theme appearance', fileName: 'app_dark_theme',
  builder: () => GoldenTestGroup(children: [
    GoldenTestScenario(name: 'empty chat',
      child: const SizedBox(width: 1200, height: 800, child: ChatScreen())),
  ]));
```

---

#### Task 1.10: Linux Desktop Build Tested

**Integration Test (`integration_test/basic_chat_test.dart`):**

```dart
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('app launches and shows empty state', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('chat_input')), findsOneWidget);
    expect(find.byKey(const Key('send_button')), findsOneWidget);
    expect(find.text('New Chat'), findsOneWidget);
  });

  testWidgets('typing in input enables send button', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    final sendBefore = tester.widget<IconButton>(find.byKey(const Key('send_button')));
    expect(sendBefore.onPressed, isNull);
    await tester.enterText(find.byKey(const Key('chat_input')), 'Hello');
    await tester.pump();
    final sendAfter = tester.widget<IconButton>(find.byKey(const Key('send_button')));
    expect(sendAfter.onPressed, isNotNull);
  });
}
```

Run: `flutter test integration_test/ -d linux`

---

#### Task 1.11: Android APK Tested

```bash
# Build
flutter build apk --debug
# Verify file exists and has non-trivial size
ls -lh build/app/outputs/flutter-apk/app-debug.apk
# Should be > 20MB
```

For device testing: `flutter install -d <android-device-id>` then manually verify app launches, connects to Amber (on same WiFi), sends a message, receives a response.

---

### Phase 2 — Streaming & Polish

#### Task 2.1: SSE Streaming Endpoint on Amber Side

ADK already provides `POST /run_sse` (confirmed from source). No server-side changes needed. Enable it in the Flutter client by switching from `sendMessage()` to `sendMessageSse()` from Section 5.2.

**Test (`test/services/sse_streaming_test.dart`):**
```dart
test('sendMessageSse yields tokens then completes', () async {
  // Mock the http.Client to return a fake SSE stream
  final fakeBody = [
    'data: {"content":{"parts":[{"text":"Hello"}]},"partial":true}\n\n',
    'data: {"content":{"parts":[{"text":" world"}]},"partial":true}\n\n',
    'data: {"turn_complete":true}\n\n',
  ];
  when(mockHttpClient.send(any)).thenAnswer((_) async =>
    http.StreamedResponse(
      Stream.fromIterable(fakeBody.map((s) => utf8.encode(s))),
      200));

  final tokens = <String>[];
  await for (final t in client.sendMessageSse(userId: 'u', sessionId: 's', text: 'hi')) {
    tokens.add(t);
  }
  expect(tokens, equals(['Hello', ' world']));
});

test('sendMessageSse throws on ADK error event', () async {
  final errorBody = 'data: {"error_code":500,"error_message":"Tool failed"}\n\n';
  when(mockHttpClient.send(any)).thenAnswer((_) async =>
    http.StreamedResponse(Stream.value(utf8.encode(errorBody)), 200));
  expect(() => client.sendMessageSse(userId: 'u', sessionId: 's', text: 'hi').toList(),
    throwsA(isA<Exception>()));
});
```

---

#### Task 2.2: Word-by-Word Streaming Animation

**Implementation:**

Use `flutter_streaming_text_markdown` for assistant messages currently streaming:

```dart
// In ChatBubble, when message is being streamed:
StreamingTextMarkdown(
  stream: tokenStream,  // Stream<String> from AdkClient.sendMessageSse()
  animationPreset: AnimationPreset.claude,
  style: const TextStyle(color: Colors.white, fontSize: 15),
  onComplete: () => ref.read(chatProvider.notifier).markStreamComplete(messageId),
)
```

Fallback: `StreamBuilder<String>` with debounced `MarkdownWidget` rebuild:
```dart
StreamBuilder<String>(
  stream: _tokenStream,
  builder: (ctx, snap) {
    if (snap.hasData) _buffer.write(snap.data);
    return MarkdownWidget(data: _buffer.toString());
  },
)
```

**Tests:**
```dart
testWidgets('streaming message updates content incrementally', (tester) async {
  final controller = StreamController<String>();
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: StreamingChatBubble(
    stream: controller.stream,
  ))));
  controller.add('Hello');
  await tester.pump();
  expect(find.textContaining('Hello'), findsOneWidget);
  controller.add(' world');
  await tester.pump();
  expect(find.textContaining('Hello world'), findsOneWidget);
  await controller.close();
});

testWidgets('streaming cursor removed after stream closes', (tester) async {
  final controller = StreamController<String>();
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: StreamingChatBubble(
    stream: controller.stream,
  ))));
  controller.add('Done');
  await tester.pump();
  expect(find.textContaining('▋'), findsOneWidget);
  await controller.close();
  await tester.pump();
  expect(find.textContaining('▋'), findsNothing);
});
```

---

#### Task 2.3: File/Image Attachment

**Implementation:**

Use `file_picker` package on desktop, `image_picker` on Android. Convert to base64 and include in ADK message as `inline_data`:

```dart
Future<void> _attachFile() async {
  final result = await FilePicker.platform.pickFiles(
    type: FileType.custom,
    allowedExtensions: ['jpg', 'png', 'pdf', 'txt', 'md'],
  );
  if (result == null) return;
  final bytes = result.files.single.bytes!;
  final base64Data = base64Encode(bytes);
  final mimeType = _mimeFromExtension(result.files.single.extension!);
  // Include as inline_data part in ADK message
}
```

**Tests:**
```dart
test('base64 encoding round-trips correctly', () {
  final original = Uint8List.fromList([1, 2, 3, 4, 5]);
  final encoded = base64Encode(original);
  final decoded = base64Decode(encoded);
  expect(decoded, equals(original));
});
```

---

#### Tasks 2.4–2.6: Multi-Platform Builds + Theme Toggle

**Linux:** Already working from Phase 1.
**Windows:** `flutter config --enable-windows-desktop && flutter build windows --debug`
**macOS:** `flutter config --enable-macos-desktop && flutter build macos --debug`

**Theme toggle test:**
```dart
testWidgets('theme toggle switches between dark and light', (tester) async {
  await tester.pumpWidget(const ProviderScope(child: AmbientApp()));
  final scaffold = tester.widget<Scaffold>(find.byType(Scaffold).first);
  expect(scaffold.backgroundColor, equals(const Color(0xFF212121))); // dark
  await tester.tap(find.byKey(const Key('theme_toggle')));
  await tester.pumpAndSettle();
  final scaffoldAfter = tester.widget<Scaffold>(find.byType(Scaffold).first);
  expect(scaffoldAfter.backgroundColor, isNot(equals(const Color(0xFF212121))));
});
```

---

### Phase 3 — Conversational Voice Mode

> **🔬 Research Note (2026-03-26 — auto):**
> ## Technical Note: Flutter Real-Time Microphone Capture → Python VAD/STT
> 
> ### Package Comparison
> 
> | | `record` v6.2.0 | `flutter_sound` v9.30.0 | `mic_stream` v0.7.2 |
> |---|---|---|---|
> | **Android** | Yes | Yes | Yes |
> | **Linux desktop** | Yes | Yes | **No** |
> | **Windows** | Yes | Yes | **No** |
> | **macOS** | Yes | Yes | Yes |
> | **PCM streaming** | `Stream<Uint8List>` via `startStream()` | Stream or buffer | `Stream<Uint8List>` |
> | **License** | BSD-3 | MPL-2.0 (v9) / GPL (v10+) | GPL-3.0 |
> | **Maintenance** | Active, clean API | Transitioning to "Taudio" (alpha) | "Under development" |
> | **Linux deps** | `parecord`, `pactl`, `ffmpeg` | Similar | N/A |
> 
> **Recommendation: `record`**. Only package with BSD license + all four target platforms + clean streaming API. `mic_stream` is eliminated by missing Linux/Windows. `flutter_sound` works but is heavier and in a licensing transition.
> 
> ---
> 
> ### Flutter → Python Streaming Architecture
> 
> ```
> Flutter (record) ──PCM16 over WebSocket──▶ Python Server
>                                             ├─ Silero VAD (speech detection)
>                                             └─ faster-whisper (transcription)
> ```
> 
> **Audio format (universal STT standard):** 16 kHz, 16-bit signed LE, mono, raw PCM.
> 
> #### Flutter Side
> 
> ```dart
> import 'package:record/record.dart';
> import 'package:web_socket_channel/web_socket_channel.dart';
> 
> final recorder = AudioRecorder();
> final channel = WebSocketChannel.connect(Uri.parse('ws://amber-server:8765'));
> 
> final stream = await recorder.startStream(RecordConfig(
>   encoder: AudioEncoder.pcm16bits,
>   sampleRate: 16000,
>   numChannels: 1,
>   autoGain: true,
>   noiseSuppress: true,
> ));
> 
> // Bytes are already PCM16 LE — send directly, no conversion needed
> stream.listen((chunk) => channel.sink.add(chunk));
> ```
> 
> #### Python Side
> 
> ```python
> import asyncio
> import websockets
> from silero_vad import VADIterator, load_silero_vad
> import numpy as np
> 
> model = load_silero_vad()
> vad = VADIterator(model, sampling_rate=16000)
> 
> async def handle_audio(ws):
>     buffer = bytearray()
>     async for chunk in ws:
>         buffer.extend(chunk)
>         # Process in 30ms frames (960 bytes = 480 samples × 2 bytes)
>         while len(buffer) >= 960:
>             frame = bytes(buffer[:960])
>             buffer = buffer[960:]
>             audio = np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0
>             speech_dict = vad(audio)
>             if speech_dict:  # speech segment boundary detected
>                 # Feed accumulated speech to faster-whisper
>                 pass
> 
> asyncio.run(websockets.serve(handle_audio, "0.0.0.0", 8765))
> ```
> 
> ---
> 
> ### Python Backend Stack
> 
> | Role | Package | Why |
> |---|---|---|
> | **VAD** | `silero-vad` (or `pysilero-vad` for ONNX-only) | ML-based, significantly more accurate than `webrtcvad`, lightweight |
> | **STT** | `faster-whisper` | CTranslate2 Whisper — 4x faster, lower memory than vanilla Whisper |
> | **WebSocket** | `websockets` | Async, clean API, pairs with Flutter's `web_socket_channel` |
> | **Turnkey alternative** | `RealtimeSTT` | Bundles Silero VAD + faster-whisper into one real-time pipeline |
> 
> ---
> 
> ### Key Implementation Notes
> 
> 1. **Don't convert the bytes.** `record`'s `startStream(pcm16bits)` returns raw PCM16 LE `Uint8List` — send directly over WebSocket. A common mistake (documented in record#286) is trying to cast to `Int16List` first.
> 
> 2. **VAD frame size matters.** Silero VAD expects 1536-sample chunks at 16 kHz (~96ms). `webrtcvad` expects 10/20/30ms frames. Buffer incoming WebSocket chunks to the right frame size.
> 
> 3. **Linux prerequisite.** The `record` package on Linux shells out to PulseAudio tools. Ensure `parecord`, `pactl`, and `ffmpeg` are installed — add them to your Linux setup script.
> 
> 4. **Reference project.** [VoiceStreamAI](https://github.com/alesaccoia/VoiceStreamAI) is an open-source Python server doing exactly this pipeline (WebSocket + Silero VAD + faster-whisper) — worth studying for the buffering/chunking logic.

#### Task 3.1: Replace Kokoro with XTTS v2 (now v2.5)

**TTS Engine Research (updated 2026-03-17):**

| Engine | Voice Cloning | First-chunk Latency (GPU) | CPU Viable | Notes |
|---|---|---|---|---|
| **XTTS v2.5** | ✅ 6-sec clip | ~150ms | ⚠️ Slow | v2.5 released late 2025, fixes cadence/naturalness issues. **Recommended for Amber.** |
| Kokoro-82M | ❌ No cloning | <0.3s | ✅ Yes | Fastest model available; best for CPU; cannot clone voice |
| Piper TTS | ❌ No cloning | <50ms | ✅ Yes | Embedded-grade, Raspberry Pi capable; CPU fallback only |
| StyleTTS2 | ⚠️ Limited | ~500ms | ❌ | Studio quality; too slow for real-time conversation |
| ElevenLabs | ✅ Excellent | ~500ms cloud | N/A | Cloud-only; best quality but requires subscription |

**Decision:** Use XTTS v2.5 (voice cloning required for Amber's custom voice). Fall back to Piper TTS for CPU-only environments.

**Server-side implementation (`agent_skills/xtts_service.py`):**

```python
# pip install TTS fastapi uvicorn
from TTS.api import TTS
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import torch, io, soundfile as sf

app = FastAPI()
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")

# Pre-compute and cache speaker embedding (run once)
SPEAKER_EMBEDDING = None
REFERENCE_AUDIO = "/home/chieh/ambient/vault/audio/amber_voice_reference.wav"

@app.on_event("startup")
def preload_speaker():
    global SPEAKER_EMBEDDING
    gpt_cond_latent, speaker_embedding = tts.synthesizer.tts_model.get_conditioning_latents(
        audio_path=[REFERENCE_AUDIO])
    SPEAKER_EMBEDDING = (gpt_cond_latent, speaker_embedding)

@app.post("/tts")
async def synthesize(text: str, stream: bool = True):
    if stream:
        async def audio_stream():
            chunks = tts.synthesizer.tts_model.inference_stream(
                text,
                "en",
                SPEAKER_EMBEDDING[0],
                SPEAKER_EMBEDDING[1],
                stream_chunk_size=20,
            )
            for chunk in chunks:
                buf = io.BytesIO()
                sf.write(buf, chunk.cpu().numpy(), 24000, format='RAW', subtype='PCM_16')
                yield buf.getvalue()
        return StreamingResponse(audio_stream(), media_type="audio/raw")
    else:
        wav = tts.tts(text=text, speaker_wav=REFERENCE_AUDIO, language="en")
        buf = io.BytesIO()
        sf.write(buf, wav, 24000, format='WAV')
        return Response(content=buf.getvalue(), media_type="audio/wav")
```

Run: `uvicorn xtts_service:app --port 8010 --host 0.0.0.0`

Expected latency (RTX 3090): ~200ms first chunk, ~800ms total for a 10-word sentence.

**Speaker embedding note:** `get_conditioning_latents()` takes 1-3 seconds. Pre-compute once at startup and cache. The voice sample needs to be 6+ seconds of clean audio.

**Fallback (no GPU / Piper TTS):**
```bash
pip install piper-tts
echo "Hello world" | piper --model en_US-lessac-medium --output-file - | aplay
```
RTF ~0.05-0.15 on CPU — generates much faster than real-time.

**Tests:**
```bash
# Smoke test
curl -X POST "http://localhost:8010/tts?text=Hello&stream=false" -o test.wav
python3 -c "import soundfile as sf; d, sr = sf.read('test.wav'); print(f'Duration: {len(d)/sr:.2f}s, SR: {sr}')"
# Expected: Duration ~0.5-1.0s, SR: 24000
```

---

#### Task 3.2: faster-whisper + silero-vad STT Pipeline

**Server-side (`agent_skills/stt_service.py`):**

```python
# pip install faster-whisper silero-vad sounddevice websockets
import asyncio, json, numpy as np
import websockets
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps

model = WhisperModel("medium.en", device="cuda", compute_type="float16")
vad_model = load_silero_vad()

SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # ~32ms at 16kHz

async def handle_client(websocket):
    audio_buffer = np.array([], dtype=np.float32)
    is_speech = False

    async for message in websocket:
        chunk = np.frombuffer(message, dtype=np.float16).astype(np.float32) / 32768.0
        audio_buffer = np.concatenate([audio_buffer, chunk])

        # Run VAD on latest chunk
        speech_ts = get_speech_timestamps(chunk, vad_model, sampling_rate=SAMPLE_RATE)

        if speech_ts:
            is_speech = True
        elif is_speech and len(audio_buffer) > SAMPLE_RATE:
            # Silence after speech — transcribe
            segments, _ = model.transcribe(audio_buffer, beam_size=5)
            text = " ".join(s.text for s in segments).strip()
            if text:
                await websocket.send(json.dumps({"type": "transcript", "text": text}))
            audio_buffer = np.array([], dtype=np.float32)
            is_speech = False

asyncio.run(websockets.serve(handle_client, "localhost", 8011))
```

Expected latency (medium.en, RTX 3090): ~200-500ms for a 5-second sentence.

**Flutter client (Phase 3):**
```dart
// Connect WebSocket to STT server
final channel = WebSocketChannel.connect(Uri.parse('ws://localhost:8011'));
// Send PCM chunks from microphone
// Listen for transcript events
channel.stream.listen((event) {
  final data = jsonDecode(event);
  if (data['type'] == 'transcript') {
    ref.read(chatProvider.notifier).setInputText(data['text']);
  }
});
```

**Tests:**
```python
# Unit test VAD detection
def test_vad_detects_silence():
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    ts = get_speech_timestamps(silence, vad_model, sampling_rate=SAMPLE_RATE)
    assert len(ts) == 0

def test_vad_detects_speech():
    # Load a known voice clip
    import soundfile as sf
    audio, sr = sf.read("test_voice_clip.wav")
    assert sr == SAMPLE_RATE
    ts = get_speech_timestamps(audio, vad_model, sampling_rate=SAMPLE_RATE)
    assert len(ts) > 0
```

---

#### Task 3.3: Voice Mode UI

Full-screen orb UI:
- Grey orb → idle
- Blue pulsing orb → listening (VAD detected speech start)
- Amber/gold glowing orb → Amber is speaking
- Tap orb → toggle push-to-talk vs continuous mode

**Tests:**
```dart
testWidgets('orb changes color when in listening state', (tester) async {
  await tester.pumpWidget(MaterialApp(home: VoiceOrb(state: VoiceState.listening)));
  final container = tester.widget<AnimatedContainer>(find.byType(AnimatedContainer).first);
  expect((container.decoration as BoxDecoration).color, equals(Colors.blue));
});
```

---

### Phase 4 — Device Control

Build on existing `computer_agent` sub-agent in `amber/agent.py`.

- **App launcher:** `amber_agent` uses `computer_agent` → `xdg-open <app>` on Linux
- **Screenshot stream:** New FastAPI endpoint `/screenshot` that takes a screenshot with `pyautogui.screenshot()`, returns PNG bytes. Flutter polls this every 2 seconds when in "computer control" mode and shows thumbnail.
- **OmniParser integration:** Already partially implemented server-side

#### Task 4.3: Screenshot Endpoint

**Server-side (`agent_skills/computer_control_server.py` — new endpoint added to Amber ADK server):**
```python
@app.get("/screenshot")
async def take_screenshot():
    import pyautogui, io
    from PIL import Image
    screenshot = pyautogui.screenshot()
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
```

**Server-side Tests (`test_screenshot_endpoint.py`):**
```python
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import io
from PIL import Image

def test_screenshot_endpoint_returns_png():
    resp = client.get("/screenshot")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 1000  # non-trivial PNG

def test_screenshot_is_valid_image():
    """Returned bytes must be a decodable PNG with non-zero dimensions."""
    resp = client.get("/screenshot")
    img = Image.open(io.BytesIO(resp.content))
    assert img.format == "PNG"
    assert img.width > 0 and img.height > 0

def test_screenshot_endpoint_handles_pyautogui_failure():
    """If pyautogui fails (e.g. no display), endpoint returns 503."""
    with patch("pyautogui.screenshot", side_effect=Exception("No display")):
        resp = client.get("/screenshot")
    assert resp.status_code == 503

def test_screenshot_with_headless_display():
    """
    Integration test — run under Xvfb in CI:
        xvfb-run python -m pytest test_screenshot_endpoint.py::test_screenshot_with_headless_display
    """
    resp = client.get("/screenshot")
    assert resp.status_code == 200
```

Run: `python -m pytest test_screenshot_endpoint.py -v`

#### Task 4.2: App Launcher (computer_agent → xdg-open)

**Tests (`test_app_launcher.py`):**
```python
import subprocess
from unittest.mock import patch

def test_xdg_open_is_called_with_app_name():
    with patch("subprocess.Popen") as mock_popen:
        from amber.tools.local_computer import open_application
        open_application("gedit")
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert "xdg-open" in call_args or "gedit" in call_args

def test_open_unknown_app_returns_error():
    """Opening a non-existent app should return an error message, not crash."""
    from amber.tools.local_computer import open_application
    result = open_application("__nonexistent_app_xyz__")
    assert result is not None
    assert "error" in result.lower() or "not found" in result.lower()
```

#### Flutter: Screenshot Polling Widget Test

```dart
// test/widgets/screenshot_panel_test.dart
testWidgets('screenshot panel shows image when endpoint returns PNG', (tester) async {
  final mockClient = MockAdkClient();
  when(mockClient.getScreenshot()).thenAnswer((_) async =>
    Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10]));  // PNG header

  await tester.pumpWidget(ProviderScope(
    overrides: [adkClientProvider.overrideWithValue(mockClient)],
    child: MaterialApp(home: ScreenshotPanel()),
  ));
  await tester.pump();
  expect(find.byType(Image), findsOneWidget);
});

testWidgets('screenshot panel shows error state on network failure', (tester) async {
  final mockClient = MockAdkClient();
  when(mockClient.getScreenshot()).thenThrow(Exception('Connection refused'));

  await tester.pumpWidget(ProviderScope(
    overrides: [adkClientProvider.overrideWithValue(mockClient)],
    child: MaterialApp(home: ScreenshotPanel()),
  ));
  await tester.pump();
  expect(find.byIcon(Icons.error_outline), findsOneWidget);
});
```

**End-to-End Task Tests (manual, with Amber running):**
```
4.5 "check my calendar" — Amber launches calendar app via computer_agent, screenshot appears in Flutter panel
4.6 "look up the weather" — Amber opens browser to weather site, Flutter panel updates within 2s
```
Run each by typing the phrase in the Flutter app. Verify: screenshot thumbnail updates, Amber responds with what it saw.

---

### Phase 5 — Wake Word ("Hey Amber")

**Wake Word Engine Research (updated 2026-03-17):**

| Engine | Accuracy | CPU Usage | Free/Open | Custom Phrase | Flutter Support |
|---|---|---|---|---|---|
| **Picovoice Porcupine** | 97%+ | ~0.1% | Free tier | ✅ Instant (transfer learning) | ✅ Official Flutter SDK |
| **OpenWakeWord** | Comparable | Very low (15–20 models on 1 Pi core) | ✅ Fully open | ✅ Train on synthetic speech | ⚠️ Python only, custom IPC bridge |
| Snowboy | Low | Low | ❌ Abandoned | ✅ | ❌ |
| PocketSphinx | Low | Low | ✅ Open | ⚠️ Complex | ❌ |

**Decision:** Use Picovoice Porcupine (free tier, Flutter SDK, 30-second custom model setup). If vendor lock-in becomes a concern, migrate to OpenWakeWord — it outperforms Porcupine on some benchmarks and is 100% open source.

#### Picovoice Porcupine

```python
# pip install pvporcupine pvrecorder
import pvporcupine, pvrecorder

porcupine = pvporcupine.create(
    access_key="<FREE_PICOVOICE_API_KEY>",
    keywords=["hey amber"],  # custom model downloaded from Picovoice Console
)
recorder = pvrecorder.PvRecorder(frame_length=porcupine.frame_length)
recorder.start()

while True:
    pcm = recorder.read()
    result = porcupine.process(pcm)
    if result >= 0:
        print("Wake word detected! Activating voice mode...")
        # Signal Flutter app to open voice mode via HTTP POST to localhost:8000/wake
        break
```

CPU usage: ~0.1% (Porcupine runs on a dedicated small model). Custom "Hey Amber" model is free via Picovoice Console (requires account, 30-second setup).

**Tests:**
```python
# test_wake_word.py
import pvporcupine
import numpy as np
import pytest

ACCESS_KEY = os.environ["PICOVOICE_ACCESS_KEY"]  # Set in .env

def test_porcupine_loads_without_error():
    p = pvporcupine.create(access_key=ACCESS_KEY, keywords=["hey amber"])
    assert p.sample_rate == 16000
    assert p.frame_length > 0
    p.delete()

def test_porcupine_no_detection_on_silence():
    """Silence frames should not trigger wake word."""
    p = pvporcupine.create(access_key=ACCESS_KEY, keywords=["hey amber"])
    silent_frame = np.zeros(p.frame_length, dtype=np.int16).tolist()
    result = p.process(silent_frame)
    assert result < 0, "False positive: silence triggered wake word detection"
    p.delete()

def test_porcupine_no_detection_on_noise():
    """Random noise frames should not trigger wake word."""
    p = pvporcupine.create(access_key=ACCESS_KEY, keywords=["hey amber"])
    rng = np.random.default_rng(42)
    for _ in range(50):
        noise_frame = rng.integers(-100, 100, p.frame_length, dtype=np.int16).tolist()
        result = p.process(noise_frame)
        assert result < 0, "False positive on noise"
    p.delete()

def test_wake_signal_http_endpoint_reachable():
    """The /wake endpoint that the daemon will call must exist."""
    import requests
    resp = requests.get("http://localhost:8000/health")
    assert resp.status_code == 200  # Server is up before testing wake integration

def test_daemon_process_starts_and_stops():
    """ambient_standby.py should start, run for 2 seconds, and exit cleanly on SIGTERM."""
    import subprocess, signal, time
    proc = subprocess.Popen(
        ["python", "/home/chieh/vessence/agent_skills/ambient_standby.py", "--test-mode"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(2)
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)
    assert proc.returncode in (0, -15), f"Unexpected exit code: {proc.returncode}"
```

Run all wake word tests: `python -m pytest test_wake_word.py -v`
Expected: All 5 tests pass. Note: `test_porcupine_no_detection_on_noise` may rarely fail due to random seed — re-run once to confirm.

**Manual validation:** Record yourself saying "Hey Amber" once and play it back through `aplay`. Confirm the daemon prints "Wake word detected!" within 500ms of the phrase ending.

---

### Phase 6 — Remote Access & Polish

#### Task 6.1: Tailscale Remote Access

- Install Tailscale on Linux machine + Android device. Both join the same tailnet.
- App settings "Server URL" field accepts a Tailscale IP (`http://100.x.x.x:8000`) in addition to localhost.
- No port forwarding needed. Encrypted mesh VPN — Amber server is never exposed to the internet.

**Setup steps:**
```bash
# Linux server
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4  # Note this IP, enter it in the Flutter app settings

# Verify connectivity from Android (Tailscale app installed):
curl http://<tailscale-ip>:8000/health
```

**Tests:**
```python
# test_remote_connectivity.py
def test_health_endpoint_responds_on_tailscale_ip():
    """
    Manual integration test. Run only when Tailscale is active.
    Set TAILSCALE_IP in environment.
    """
    import os, requests
    ip = os.environ.get("TAILSCALE_IP")
    if not ip:
        pytest.skip("TAILSCALE_IP not set — skipping remote connectivity test")
    resp = requests.get(f"http://{ip}:8000/health", timeout=5)
    assert resp.status_code == 200
```

```dart
// test/unit/services/adk_client_remote_test.dart
test('AdkClient works with non-localhost base URL', () async {
  final client = AdkClient(baseUrl: 'http://100.1.2.3:8000');
  // Just verify it constructs without error and uses the correct URL
  expect(client.baseUrl, equals('http://100.1.2.3:8000'));
});

test('settings screen saves and restores custom server URL', () async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('server_url', 'http://100.1.2.3:8000');
  // Re-read
  expect(prefs.getString('server_url'), equals('http://100.1.2.3:8000'));
});
```

---

#### Task 6.3: Vault Browser Screen

**New ADK endpoint (`amber/agent.py` or dedicated FastAPI route):**
```python
@app.get("/vault/list")
async def vault_list():
    """Return all vault files grouped by type."""
    vault_root = Path(VAULT_PATH)
    files = []
    for f in vault_root.rglob("*"):
        if f.is_file():
            rel = f.relative_to(vault_root)
            category = rel.parts[0] if len(rel.parts) > 1 else "misc"
            files.append({
                "path": str(rel),
                "category": category,
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })
    return {"files": sorted(files, key=lambda x: x["modified"], reverse=True)}

@app.get("/vault/get/{filepath:path}")
async def vault_get(filepath: str):
    """Serve a vault file by relative path."""
    full_path = Path(VAULT_PATH) / filepath
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Security: ensure path doesn't escape vault root
    if not str(full_path.resolve()).startswith(str(Path(VAULT_PATH).resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(full_path)
```

**Server-side Tests (`test_vault_endpoints.py`):**
```python
def test_vault_list_returns_json():
    resp = client.get("/vault/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert isinstance(data["files"], list)

def test_vault_list_groups_by_category():
    resp = client.get("/vault/list")
    files = resp.json()["files"]
    categories = {f["category"] for f in files}
    # Expect standard vault categories to be present if vault has content
    expected = {"images", "documents", "pdf", "audio"}
    assert len(categories) > 0

def test_vault_get_returns_file():
    # First get the list to find a real file
    resp = client.get("/vault/list")
    files = resp.json()["files"]
    if not files:
        pytest.skip("Vault is empty")
    first_file = files[0]["path"]
    dl_resp = client.get(f"/vault/get/{first_file}")
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0

def test_vault_get_missing_file_returns_404():
    resp = client.get("/vault/get/nonexistent/file.xyz")
    assert resp.status_code == 404

def test_vault_get_path_traversal_blocked():
    """Security: ../../etc/passwd should be rejected."""
    resp = client.get("/vault/get/../../etc/passwd")
    assert resp.status_code in (403, 404)
```

**Flutter Widget Tests:**
```dart
// test/widgets/vault_browser_test.dart
testWidgets('vault browser shows files grouped by category', (tester) async {
  final mockClient = MockAdkClient();
  when(mockClient.listVaultFiles()).thenAnswer((_) async => [
    VaultFile(path: 'images/photo.jpg', category: 'images', filename: 'photo.jpg'),
    VaultFile(path: 'documents/notes.txt', category: 'documents', filename: 'notes.txt'),
  ]);

  await tester.pumpWidget(ProviderScope(
    overrides: [adkClientProvider.overrideWithValue(mockClient)],
    child: MaterialApp(home: VaultBrowserScreen()),
  ));
  await tester.pump();
  expect(find.text('images'), findsOneWidget);
  expect(find.text('documents'), findsOneWidget);
  expect(find.text('photo.jpg'), findsOneWidget);
});

testWidgets('tapping a file triggers download', (tester) async {
  final mockClient = MockAdkClient();
  when(mockClient.listVaultFiles()).thenAnswer((_) async => [
    VaultFile(path: 'documents/notes.txt', category: 'documents', filename: 'notes.txt'),
  ]);
  when(mockClient.downloadVaultFile(any)).thenAnswer((_) async => Uint8List(0));

  await tester.pumpWidget(ProviderScope(
    overrides: [adkClientProvider.overrideWithValue(mockClient)],
    child: MaterialApp(home: VaultBrowserScreen()),
  ));
  await tester.pump();
  await tester.tap(find.text('notes.txt'));
  await tester.pump();
  verify(mockClient.downloadVaultFile('documents/notes.txt')).called(1);
});
```

Run: `flutter test test/widgets/vault_browser_test.dart`

#### Task 6.4: iOS Build (Optional)

```bash
# Requires macOS with Xcode 15+
flutter config --enable-ios
flutter build ios --debug --no-codesign
```
Expected: Build succeeds without errors. Test on iPhone Simulator: `flutter run -d "iPhone 15"`

**Integration validation checklist:**
- [ ] App launches on iOS Simulator without crash
- [ ] Can connect to Amber server at the configured URL
- [ ] Send a message and receive a response
- [ ] Conversation history persists after app backgrounding

---

## 9. Comprehensive Testing Strategy

### 9.1 Testing Pyramid

```
           ┌─────────────┐
           │ Integration │  Few, slow, high confidence
           │     Tests   │  (real app on real platform)
           └──────┬──────┘
          ┌───────┴────────┐
          │  Widget Tests  │  Moderate, fast
          │ (component UI) │
          └───────┬────────┘
    ┌─────────────┴──────────────┐
    │    Unit Tests (pure logic) │  Many, very fast
    └────────────────────────────┘
```

### 9.2 Test File Structure

```
test/
  unit/
    services/
      adk_client_test.dart
      session_manager_test.dart
      database_test.dart
      sse_event_parser_test.dart
      connection_manager_test.dart
    models/
      message_test.dart
      conversation_test.dart
  widget/
    chat_bubble_test.dart
    input_bar_test.dart
    sidebar_test.dart
    connection_banner_test.dart
    settings_screen_test.dart
  golden/
    chat_bubble_golden_test.dart
    app_dark_theme_golden_test.dart
integration_test/
  basic_chat_test.dart
  conversation_flow_test.dart
  settings_test.dart
```

### 9.3 Running Tests

```bash
# All unit + widget tests
flutter test test/

# With coverage
flutter test --coverage test/
genhtml coverage/lcov.info -o coverage/html

# Specific test file
flutter test test/unit/services/adk_client_test.dart

# Integration tests on Linux
flutter test integration_test/ -d linux

# Generate goldens (Linux only — never macOS, fonts differ)
flutter test --update-goldens test/golden/

# Verify goldens
flutter test test/golden/
```

### 9.4 What to Test Per Layer

**Unit tests** (pure Dart, no Flutter framework, fastest):
- `SseEventParser.feed()` — handles chunked delivery, malformed JSON, `[DONE]` sentinel
- `MessageRepository` — all CRUD operations, pagination, cascade delete
- `ConversationRepository` — groupByDate logic, sort order
- `SessionManager` — creates new session when none exists, reuses valid session, creates new when stale
- `AdkClient` — all HTTP success/error cases with mocked `Dio`/`http.Client`
- `AdkConnectionManager` — online→offline→online transitions, debounce behavior

**Widget tests** (Flutter test framework, no real platform):
- `ChatBubble` — alignment by role, markdown renders, code block has copy button, streaming cursor shows/hides
- `InputBar` — send disabled on empty, enabled on text, onSend called with trimmed text, input cleared after send
- `Sidebar` — date grouping, active conversation highlighted, delete confirmation
- `ConnectionBanner` — shows on offline, hides on online, animates transition
- `SettingsScreen` — server URL persisted, validates URL format

**Golden tests** (screenshot regression, Linux only):
- Full app dark theme with empty chat
- Chat bubble variants (user, assistant, code block, streaming)
- Sidebar with multiple conversation groups
- Connection offline state

**Integration tests** (real compiled app on Linux):

`integration_test/basic_chat_test.dart` — already defined in Task 1.10.

`integration_test/conversation_flow_test.dart`:
```dart
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('new chat creates a new conversation entry in sidebar', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    // Count initial conversations
    final initial = find.byType(ConversationTile).evaluate().length;
    // Tap "New Chat"
    await tester.tap(find.byKey(const Key('new_chat_button')));
    await tester.pumpAndSettle();
    // Type and send a message to create the conversation
    await tester.enterText(find.byType(TextField), 'Test message for new conversation');
    await tester.tap(find.byKey(const Key('send_button')));
    await tester.pumpAndSettle(const Duration(seconds: 3));
    // Sidebar should now have one more conversation
    expect(find.byType(ConversationTile).evaluate().length, greaterThan(initial));
  });

  testWidgets('switching conversations loads correct messages', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    // Assumes at least 2 existing conversations from previous test or seeded DB
    final tiles = find.byType(ConversationTile);
    if (tiles.evaluate().length < 2) return;  // Skip if not enough conversations
    await tester.tap(tiles.at(0));
    await tester.pumpAndSettle();
    final firstContent = find.byType(ChatBubble).evaluate().length;
    await tester.tap(tiles.at(1));
    await tester.pumpAndSettle();
    final secondContent = find.byType(ChatBubble).evaluate().length;
    // Different conversations may have different message counts
    expect(firstContent + secondContent, greaterThan(0));
  });

  testWidgets('conversation history survives app restart', (tester) async {
    // Phase 1: send a message
    app.main();
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Remember this: persistence test');
    await tester.tap(find.byKey(const Key('send_button')));
    await tester.pumpAndSettle(const Duration(seconds: 2));
    // Phase 2: restart the app widget tree
    await tester.restartApp();
    await tester.pumpAndSettle();
    // The message should still be in history
    expect(find.textContaining('Remember this: persistence test'), findsOneWidget);
  });
}
```

`integration_test/settings_test.dart`:
```dart
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('can change server URL in settings and it persists', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    // Navigate to settings
    await tester.tap(find.byKey(const Key('settings_button')));
    await tester.pumpAndSettle();
    // Clear and type new URL
    final urlField = find.byKey(const Key('server_url_field'));
    await tester.tap(urlField);
    await tester.pump();
    await tester.enterText(urlField, 'http://192.168.1.100:8000');
    await tester.tap(find.byKey(const Key('save_settings_button')));
    await tester.pumpAndSettle();
    // Restart app and verify URL was persisted
    await tester.restartApp();
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings_button')));
    await tester.pumpAndSettle();
    expect(find.text('http://192.168.1.100:8000'), findsOneWidget);
  });

  testWidgets('invalid server URL shows validation error', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings_button')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('server_url_field')), 'not-a-url');
    await tester.tap(find.byKey(const Key('save_settings_button')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Invalid URL'), findsOneWidget);
  });
}
```

Run all integration tests: `xvfb-run flutter test integration_test/ -d linux`

### 9.5 CI/CD (GitHub Actions)

```yaml
name: Flutter CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with: { channel: stable, cache: true }
      - run: sudo apt-get install -y ninja-build libgtk-3-dev libx11-dev pkg-config cmake clang libsqlite3-dev libsecret-1-dev
      - run: flutter pub get
      - run: flutter analyze
      - run: flutter test --coverage test/
      - run: flutter config --enable-linux-desktop
      - run: xvfb-run flutter test integration_test/ -d linux
      - run: xvfb-run flutter test test/golden/
```

### 9.6 Fakes for Audio Services

Since `record`, `just_audio`, and `web_socket_channel` use platform channels that throw `MissingPluginException` in tests, always inject via interface:

```dart
abstract class AudioService {
  Future<void> startRecording();
  Future<String?> stopRecording();  // Returns file path or null
  Future<void> playUrl(String url);
  Future<void> stop();
}

class FakeAudioService implements AudioService {
  final List<String> playedUrls = [];
  bool isRecording = false;

  @override Future<void> startRecording() async => isRecording = true;
  @override Future<String?> stopRecording() async { isRecording = false; return '/tmp/test.wav'; }
  @override Future<void> playUrl(String url) async => playedUrls.add(url);
  @override Future<void> stop() async {}
}
```

---

## 10. Open Questions (Must Answer Before Coding)

> **Visual / UI questions are not listed here.** All visual defaults (font: Inter 15px, accent: light green #86EFAC matching Chieh's preference, avatar: illustrated amber-toned circle, dark theme: ChatGPT-style #212121, code theme: VS Code Dark+, animations: Claude.ai-style smooth, density: comfortable, timestamps: hover-only, avatar: first-in-group only) are set to current industry best practice and made adjustable via `ThemeConfig` in settings. Change later if needed — no approval required.

---

### A. Framework
1. **Flutter confirmed?** Comfortable learning Dart, or prefer TypeScript stack (Tauri + React)?
2. **iOS target?** Phase 6 or skip entirely?

---

### B. Network & Discovery
3. **Remote access:** Tailscale mesh VPN (recommended — zero-config, works through NAT) vs Cloudflare Tunnel vs local-only? Each has trade-offs for latency, setup complexity, and whether Chieh wants Amber accessible from, e.g., Northeastern campus.
4. **Server discovery:** Auto-detect Amber via mDNS/Bonjour on local network, or enter the IP once manually in settings? mDNS requires a running Avahi daemon on the Linux server.

---

### C. Authentication
5. **Access control:** Simple shared `AMBER_API_KEY` header checked by the ADK wrapper, or no auth and rely entirely on network isolation (LAN/Tailscale only)? Determines whether a lost/stolen Android device could talk to Amber.

---

### D. Conversation & History Behavior
6. **History location:** Device-local SQLite (each device keeps its own history, simpler, no sync) vs server-side DB shared across devices (requires a sync API on the server side). Affects Phase 1 architecture significantly.
7. **Multiple conversations or one thread?** Sidebar with named conversations (ChatGPT-style) vs a single continuous infinite scroll (iMessage-style). Determines whether conversations need titles, creation timestamps, and a delete flow.
8. **Conversation title generation:** When a new conversation starts, auto-generate a title from the first message (requires a second LLM call) vs user types a title manually vs just use the date/time as default?
9. **Context sent per message:** When Chieh sends a message in an existing conversation, does the app send the full conversation history to ADK each time (for continuity), or only the new message and rely on the ADK session to hold context? What is the max history depth to send before truncating?
10. **Message editing:** Can Chieh edit a sent message? If yes, does re-submitting the edit re-run Amber's response and discard everything after that point (like Claude.ai), or append a new exchange below?
11. **Message deletion:** Can individual messages be deleted from the local history? Does deleting a user message also delete the paired Amber response?
12. **Conversation export:** Should the app support exporting a conversation as plain text, markdown, or PDF? If yes, triggered from where (long-press, overflow menu)?
13. **Cross-device sync:** If Chieh runs the app on both Linux desktop and Android, should conversations sync between devices? If yes, what is the sync mechanism (server push, manual pull, realtime WebSocket)?

---

### E. Input Behavior
14. **Send key:** Enter to send (like most chat apps) vs Shift+Enter to send / Enter for newline (like Slack)? On mobile, the on-screen keyboard Send button always sends regardless.
15. **Input history:** Arrow-up to recall the last sent message (like a terminal) — useful for quick edits and retries?
16. **Drag-and-drop / paste images:** Can Chieh paste a screenshot or drag an image file into the input bar to send it to Amber? If yes, Amber must be multimodal — is she configured for image input?
17. **File attachments:** Can Chieh attach files (PDFs, code files, etc.) from the app directly? Or is file sending Discord-only for now?
18. **Input bar max height:** As Chieh types a long message, does the input bar expand to show the full text (up to ~6 lines), then scroll — or is it always single-line with horizontal scroll?

---

### F. Amber Response Behavior
19. **Streaming in Phase 1?** ADK `/run_sse` is already implemented and tested. Starting with streaming in Phase 1 gives a significantly better first impression. Tradeoff: slightly more complex than a simple `/run` call. Recommendation: yes, Phase 1.
20. **Mid-stream cancellation:** Can Chieh tap a Stop button to cancel Amber's response mid-stream? If yes, is the partial response kept in history or discarded?
21. **Error display:** If ADK returns an error (timeout, 5xx, malformed JSON), should the app show the raw error message in the chat bubble, a friendly "Amber had a problem, try again" message with a Retry button, or both?
22. **Offline / server-down behavior:** When the Amber server is unreachable, should the app show a persistent offline banner, queue messages for retry when back online, or immediately return an error bubble? Queuing is friendlier but complex.
23. **Amber thinking steps visibility:** ADK can return intermediate "thinking" steps before the final answer. Should these be visible in the UI (collapsed by default, expandable like Claude.ai's reasoning), or hidden entirely?
24. **Proactive messages from Amber:** Amber can push notifications via Discord today. Should the app also receive Amber-initiated messages directly (requires a persistent WebSocket or polling from the server)? If yes, where do they appear — in the current conversation or a special "Amber says" thread?
25. **Response regeneration:** Should there be a Regenerate button on Amber's last response to get a fresh answer? Does this discard the old response or append a new one?

---

### G. Voice Behavior
26. **TTS engine:** XTTS v2 (local, voice cloning, ~300ms first-chunk latency) vs ElevenLabs (cloud, best quality, API cost) vs Piper TTS (CPU-only, ~50ms, robotic but fast)? Can be set per-device in settings.
27. **Amber's voice:** Use a built-in XTTS speaker embedding, or record a custom voice sample to clone? Custom voice requires ~30s of clean audio from Chieh/you.
28. **Voice input language:** English-only (faster-whisper `base.en` model, ~80ms) or multilingual (faster-whisper `small`, ~200ms, supports Mandarin if Chieh speaks it)?
29. **Voice mode activation:** Full-duplex (always listening after wake word, can interrupt Amber mid-speech) vs push-to-talk (hold a button)? Full-duplex requires echo cancellation to avoid Amber's TTS output triggering the STT.
30. **Auto-send after STT:** When voice input finishes (detected by VAD silence), does it auto-send immediately, or show the transcribed text in the input bar for Chieh to review and confirm first?
31. **TTS for all messages:** Does Amber speak every response aloud when voice mode is on, or only responses to voice-initiated messages? Long code/technical responses may be awkward to hear.
32. **Interruption behavior:** If Chieh speaks while Amber is talking, does the app immediately stop playback and process the new input, or finish the current sentence first?
33. **Voice mode on Android background:** When the app is backgrounded on Android, does the wake word listener keep running (requires a foreground service with persistent notification), or suspend until app is foregrounded?

---

### H. Wake Word
34. **Wake phrase:** "Amber", "Hey Amber", or a custom phrase? Custom requires re-training a Porcupine keyword model (free, ~5 min online tool). "Amber" alone may have false triggers from ambient speech.
35. **Platform priority:** Linux desktop wake word first, or Android? The two use different microphone APIs (ALSA/PulseAudio vs Android AudioRecord).
36. **Linux microphone:** Use system default input device, or let Chieh pick a specific device in settings (important if there are multiple mics or a USB headset)?
37. **Post-response return to standby:** After Amber finishes speaking, how long does the app stay in "active listening" mode before returning to wake-word-only standby? Options: immediate, 10s, 30s, configurable.
38. **Visual wake word feedback:** When the wake word is detected, show a visual indicator (pulsing mic icon, status bar change) so Chieh knows Amber heard him without audio feedback?

---

### I. Device Control (Phase 5)
39. **App control scope:** All installed apps visible in a launcher grid, or a curated allow-list Chieh configures? Full list is simpler to build but cluttered. Allow-list is safer and cleaner.
40. **Screenshot stream in-app:** Show Amber a live screenshot feed so she can assist with what's on screen, or only on explicit "take screenshot" command? Live feed has privacy/battery implications on Android.
41. **Computer control confirmation:** When Amber executes a computer action (click, type, run command), should the app show a preview step ("Amber wants to click X — Allow?") or execute immediately? Immediate is faster but less safe.

---

### J. Notifications
42. **Desktop notifications:** Show an OS notification when Amber sends a proactive message while the app is backgrounded? Requires `flutter_local_notifications` + platform permission on Android.
43. **Notification tap behavior:** Tapping a notification opens the app — does it navigate directly to the relevant conversation/message, or just open the app to wherever it was last?
44. **Notification sound:** Use system default sound, a custom Amber-specific chime, or silent (badge only)?
45. **Do Not Disturb passthrough:** Should Amber's messages bypass Android DND for high-priority notifications (e.g., Amber detects something important), or always respect DND?

---

### K. Multi-User & Sessions
46. **ADK session lifecycle:** The ADK session ID persists Amber's context. Should the app create one session per conversation (clean context per chat) or one long-running session across all conversations? One-per-conversation is cleaner but loses cross-conversation awareness unless history is explicitly re-injected.
47. **Session recovery after crash:** If the app crashes mid-conversation, should it try to resume the same ADK session (may have stale state) or start a fresh session and re-inject the last N messages as context?
48. **Multi-user:** Is this single-user (Chieh only) for now, or should the app support spouse or Emily having their own conversation history on the same device?

---

## 11. Progress Tracker

### Pre-Development
- [x] Spec written (2026-03-17)
- [x] Technology stack researched and documented
- [x] Test strategy defined for all phases
- [x] Visual/UI defaults set to industry standard (adjustable via ThemeConfig — no approval needed)
- [ ] Open questions answered (Section 10) — 48 functionality behavior questions across 11 categories
- [ ] TTS engine selected and tested

### Phase 1 — Core Chat (MVP)
- [x] 1.1 Flutter project scaffold (Linux + Android targets configured)
- [x] 1.2 ADK HTTP client (create session, send message, receive response)
- [x] 1.3 Chat bubble UI (user right, Amber left, markdown, code blocks + copy)
- [x] 1.4 Input bar (text field, send button, disabled state)
- [x] 1.5 Sidebar (conversation list, new chat, delete, date grouping)
- [x] 1.6 Local SQLite conversation persistence (conversations + messages tables)
- [ ] 1.7 Connection status indicator (ping loop, offline banner)
- [ ] 1.8 Settings screen (server URL, display name)
- [ ] 1.9 Dark theme (ChatGPT-style)
- [ ] 1.10 Linux desktop build tested
- [ ] 1.11 Android APK tested on device

### Phase 2 — Streaming & Polish
- [ ] 2.1 SSE streaming enabled (switch to /run_sse, token-by-token display)
- [ ] 2.2 Word-by-word typewriter animation
- [ ] 2.3 File attachment (image + document, base64 to ADK)
- [ ] 2.4 Inline image display in chat
- [ ] 2.5 Windows build tested
- [ ] 2.6 macOS build tested
- [ ] 2.7 Light/dark theme toggle
- [ ] 2.8 App icon and splash screen
- [ ] 2.9 Conversation auto-naming (from first user message)

### Phase 3 — Conversational Voice Mode
- [ ] 3.1 TTS engine replaced (XTTS v2 or selected alternative)
- [ ] 3.2 XTTS FastAPI service running on localhost:8010
- [ ] 3.3 faster-whisper STT + WebSocket server on localhost:8011
- [ ] 3.4 silero-vad Voice Activity Detection
- [ ] 3.5 Voice mode orb UI (full-screen, animated)
- [ ] 3.6 Push-to-talk working end-to-end
- [ ] 3.7 Full-duplex + interruption handling
- [ ] 3.8 Sentence-streaming pipeline (TTS starts on first sentence)
- [ ] 3.9 All voice turns saved to chat history

### Phase 4 — Device Control
- [ ] 4.1 Computer Control mode indicator in app UI
- [ ] 4.2 App launcher: Amber opens named apps via computer_agent
- [ ] 4.3 Screenshot stream endpoint on server
- [ ] 4.4 Screenshot thumbnail displayed in app (user sees what Amber sees)
- [ ] 4.5 End-to-end task: "check my calendar"
- [ ] 4.6 End-to-end task: "look up the weather"

### Phase 5 — Standby / Wake Word
- [ ] 5.1 Picovoice Porcupine account + "Hey Amber" custom wake word model
- [ ] 5.2 ambient_standby.py daemon (PyAudio + Porcupine, Linux)
- [ ] 5.3 Daemon auto-starts on boot (systemd or cron @reboot)
- [ ] 5.4 Wake word triggers voice mode in app
- [ ] 5.5 Return to standby after 3s silence
- [ ] 5.6 Android foreground service for always-on standby
- [ ] 5.7 Visual standby indicator in app

### Phase 6 — Remote & Polish
- [ ] 6.1 Tailscale setup documented + app supports remote URL
- [ ] 6.2 Push notifications / Heart Beat integration
- [ ] 6.3 Vault browser screen
- [ ] 6.4 iOS build (optional)


---

### Research: flutter_vs_alternatives (2026-03-26)
# Cross-Platform Framework Comparison (2025–2026)

**Target platforms:** Linux, Windows, macOS, Android

---

## Comparison Matrix

| Criterion | **Flutter 3.29+** | **React Native 0.84** | **Tauri v2.10** |
|---|---|---|---|
| Linux desktop | **Stable** (since 3.0) | **Not supported** | **Stable** |
| Windows desktop | Stable | Stable (via Microsoft) | Stable |
| macOS desktop | Stable | Stable (via Microsoft) | Stable |
| Android | Stable (primary target) | Stable (primary target) | Supported (less mature) |
| Language | Dart | JS/TS | **Rust** backend + any web frontend |
| Rendering | Own engine (Impeller/Skia) | Native mobile widgets | System WebView |
| Min bundle size | ~15–20 MB | ~50+ MB | **~3–10 MB** |
| GitHub stars | ~175K | ~126K | ~105K |
| Package ecosystem | 50K+ on pub.dev | Massive npm (mobile-focused) | Growing, smaller |

---

## Framework-by-Framework Analysis

### Flutter — Recommended

- **Desktop Linux:** Stable since May 2022. Uses GTK. Hot reload works on all desktop targets. Canonical ships the **Ubuntu installer** in Flutter.
- **Android:** Flutter's original strength — mature, battle-tested, excellent tooling.
- **Ecosystem:** 50K+ pub.dev packages. Desktop-specific packages (system tray, D-Bus, XDG dirs) exist but are thinner than mobile.
- **Who uses it:** Canonical (Ubuntu), LG (webOS TVs), Google internally, BMW, Toyota.
- **Pain points:**
  - Non-native widget rendering — apps look "Flutter", not GTK/Qt.
  - Desktop bundle is ~15–20 MB minimum (bundled engine).
  - Linux has the smallest desktop share (~11% of Flutter desktop usage).
  - Multi-window, system tray, and global shortcuts rely on community packages of varying quality.
  - Dart is a smaller hiring pool than JS/TS.

### React Native — Eliminated

- **No Linux desktop support.** Community attempts (react-native-linux, React NodeGui) are unmaintained/experimental. This is a hard disqualifier for the Ambient requirement set.
- Windows and macOS are maintained by Microsoft as "out-of-tree" platforms, not the core team.
- Even if Linux weren't needed, desktop maturity lags mobile significantly (~750 open issues on RN-Windows).

### Tauri v2 — Strong Alternative

- **Desktop Linux:** First-class, stable. Uses system WebKitGTK — apps feel native.
- **Android:** Supported since Tauri 2.0 (Oct 2024), but less mature than desktop. Mobile plugins require Kotlin/Java. Desktop-only APIs (tray, global shortcuts) don't apply on mobile.
- **Bundle size:** 3–10 MB — dramatically smaller than Flutter or Electron.
- **Who uses it:** Firezone, Sourcegraph Cody, ~400 tracked companies.
- **Pain points:**
  - **Rust is mandatory** for the backend — steep learning curve, slower compile times.
  - WebView varies across OSes (WebKitGTK version on older distros can be problematic).
  - Android support is functional but the mobile plugin ecosystem is thin.
  - Smaller community = fewer tutorials, less Stack Overflow coverage.

---

## Recommendation: **Flutter**

For Ambient's requirements (Linux + Windows + macOS + Android, connecting to a local ADK server), Flutter is the right choice. Here's why:

| Factor | Why Flutter wins |
|---|---|
| **All four targets stable** | Only framework where Linux, Windows, macOS, and Android are all stable and actively maintained by the core team. |
| **Android maturity** | Android is Flutter's home turf — Tauri's Android is newer and less battle-tested. |
| **Dart ≈ good enough** | Chieh already has the spec moving in this direction. Dart is straightforward for someone with CS/ML background. |
| **Canonical precedent** | Ubuntu installer is Flutter — proves Linux desktop viability for production software. |
| **Single rendering engine** | Impeller ensures pixel-identical UI across all four platforms — no WebView inconsistency. |
| **HTTP/SSE/WebSocket** | `http`, `dio`, and `web_socket_channel` packages are mature — connecting to a local ADK server is straightforward. |

**When Tauri would be better:** If Ambient were desktop-only, or if sub-5 MB bundle size mattered, or if the team had Rust expertise. None of these apply here.

**Key Flutter risk to monitor:** Desktop plugin quality. For system tray (`tray_manager`), local notifications (`flutter_local_notifications`), and file picking (`file_picker`), verify Linux support in each package before committing to it. Pin versions aggressively.

---

### Research: flutter_chat_ui (2026-03-26)
# Flutter Chat UI Packages — Technical Note

**Context:** Project Ambient, cross-platform Flutter app connecting to local AI server.

---

## Recommended Stack

| Layer | Package | Version | Notes |
|---|---|---|---|
| Markdown rendering | `gpt_markdown` | **1.1.5** | Built for LLM output; bundled LaTeX + syntax highlighting |
| Code highlighting | *(bundled in `gpt_markdown`)* | — | Or standalone `flutter_highlight` 0.7.0 (190+ languages) |
| Streaming animation | `flutter_streaming_text_markdown` | **1.5.0** | Handles partial markdown, pause/resume, skip |
| Chat list | `ListView.builder(reverse: true)` | Flutter built-in | Custom bubbles wrapping the above |

**All-in-one alternative:** `flutter_gen_ai_chat_ui` **2.7.0** — bundles list + streaming + markdown + code highlighting, but less customizable.

---

## 1. Markdown Rendering

| Package | Version | LaTeX | Code Highlighting | Status |
|---|---|---|---|---|
| ~~`flutter_markdown`~~ | 0.7.7+1 | No | No | **Discontinued** (May 2025) |
| `flutter_markdown_plus` | 1.0.7 | No | No (manual wiring) | Active — drop-in replacement |
| **`gpt_markdown`** | 1.1.5 | Yes (`flutter_math_fork`) | Yes (built-in) | Active — purpose-built for LLM output |
| `markdown_widget` | 2.3.2+8 | Manual setup | Yes (`highlight` themes) | Active — most customizable |
| `flutter_widget_from_html` | 0.17.1 | No | No | HTML renderer, not markdown |

**Pick `gpt_markdown`** — it handles GFM tables, task lists, code fences, inline formatting, and LaTeX with zero config. Use `gpt_markdown_lite` (1.0.16) if you don't need LaTeX and want a smaller bundle.

---

## 2. Code Syntax Highlighting

| Package | Version | Languages | Notes |
|---|---|---|---|
| `flutter_highlight` | 0.7.0 | 190+ | Most common choice; uses `highlight` 0.7.0 engine |
| `flutter_highlighter` | 0.1.1 | 190+ | Newer highlight.js 11.8.0 port; early stage |
| `syntax_highlight` | 0.5.0 | 15 only | Official Dart team; VSCode-quality output |

If using `gpt_markdown`, highlighting is already included. For standalone use or custom markdown renderers, wire `flutter_highlight` into your code block builder.

---

## 3. Streaming / Typewriter Animation

| Package | Version | Incremental streaming? | Markdown during stream? |
|---|---|---|---|
| **`flutter_streaming_text_markdown`** | 1.5.0 | Yes | Yes |
| `flutter_gen_ai_chat_ui` | 2.7.0 | Yes | Yes (bundled) |
| `animated_text_kit` | 4.3.0 | **No** — needs complete string | No |

**`flutter_streaming_text_markdown`** solves the hard problems:
- Animation presets: `LLMAnimationPresets.chatGPT` (char-based fast), `.claude` (word-based smooth), `.typewriter`
- Handles partial markdown mid-stream (incomplete code fences, etc.)
- Pause, resume, skip, speed multiplier
- Does **not** restart animation when new tokens arrive

**DIY pattern** (if you want full control):
```dart
StreamBuilder<String>(
  stream: tokenStream,  // from SSE/WebSocket
  builder: (ctx, snap) {
    buffer.write(snap.data ?? '');
    return GptMarkdown(data: buffer.toString());
  },
)
```
Downside: full widget rebuild per token causes flicker on complex markdown. The dedicated package avoids this.

---

## 4. Chat List Performance

**Use `ListView.builder(reverse: true)`** — this is what ChatGPT, the Flutter AI Toolkit, and `flutter_chat_ui` all use internally.

Key tips:
- `reverse: true` pins scroll to bottom automatically; new messages appear without `jumpTo(maxScrollExtent)`
- `shrinkWrap: false` (default) — never set `true` in a chat list
- `addAutomaticKeepAlives: false` if messages are stateless
- **Avoid** `CustomScrollView` with many slivers — known performance regression at depth (flutter/flutter#168442)

Pre-built chat scaffolds if you don't want to build your own:

| Package | Version | Verdict |
|---|---|---|
| `flutter_chat_ui` (Flyer Chat) | 2.11.1 | Most mature; needs custom builder for `gpt_markdown` rendering |
| `dash_chat_2` | 0.0.21 | Quick prototyping only; v0.0.x maturity |
| `flutter_gen_ai_chat_ui` | 2.7.0 | Best for AI chat specifically; less customizable |

---

## For Ambient: Suggested `pubspec.yaml` Additions

```yaml
dependencies:
  gpt_markdown: ^1.1.5
  flutter_streaming_text_markdown: ^1.5.0
  # Only if you need standalone code highlighting outside markdown:
  # flutter_highlight: ^0.7.0
```

Build the chat list with `ListView.builder(reverse: true)` and custom bubble widgets. Use `gpt_markdown` for completed messages, `flutter_streaming_text_markdown` for the actively-streaming message. This gives you maximum control over the UI while leveraging battle-tested rendering for the hard parts (markdown, LaTeX, code, streaming).

---

### Research: adk_sse_streaming (2026-03-26)
# SSE Streaming for Google ADK → Flutter

## 1. ADK's Native Streaming

Google ADK's `Runner.run_async()` yields `Event` objects. The key is to wrap this async generator in a Starlette `EventSourceResponse`.

```bash
pip install sse-starlette>=2.0.0
```

## 2. FastAPI SSE Endpoint

```python
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import json

app = FastAPI()

async def adk_event_generator(runner: Runner, user_id: str, session_id: str, message: str):
    """Wrap ADK's async generator as SSE events."""
    from google.genai.types import Content, Part

    user_content = Content(parts=[Part(text=message)], role="user")

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_content,
    ):
        # Each ADK event has .author and .content
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    yield {
                        "event": "token",
                        "data": json.dumps({
                            "author": event.author,
                            "text": part.text,
                            "partial": True,
                        }),
                    }
                elif part.function_call:
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args),
                        }),
                    }
                elif part.function_response:
                    yield {
                        "event": "tool_result",
                        "data": json.dumps({
                            "name": part.function_response.name,
                            "result": dict(part.function_response.response),
                        }),
                    }

    # Signal completion
    yield {"event": "done", "data": json.dumps({"finished": True})}


@app.get("/api/chat/stream")
async def stream_chat(request: Request, message: str, session_id: str = "default"):
    """SSE endpoint that streams ADK responses token-by-token."""

    async def event_stream():
        async for chunk in adk_event_generator(runner, "user-1", session_id, message):
            # Check if client disconnected
            if await request.is_disconnected():
                break
            yield chunk

    return EventSourceResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

## 3. Critical Detail: ADK Streaming vs. Chunked Tokens

ADK's `run_async()` yields **complete agent turns**, not individual tokens. Each `Event` is a full response from one agent step. For true token-level streaming, you need to use ADK with the Gemini model's streaming mode:

```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    name="amber",
    model="gemini-2.0-flash",
    instruction="...",
    # ADK passes generate_content_config to the model
    generate_content_config={
        "response_modalities": ["TEXT"],
    },
)

# The runner must be created with streaming enabled
runner = Runner(
    agent=agent,
    app_name="ambient",
    session_service=InMemorySessionService(),
)

# run_async with streaming=True yields partial text chunks
async for event in runner.run_async(
    user_id=user_id,
    session_id=session_id,
    new_message=user_content,
    run_config=RunConfig(streaming_mode=StreamingMode.SSE),
):
    # event.partial=True for intermediate chunks
    ...
```

## 4. Flutter Client (`http` + manual SSE parsing or `flutter_client_sse`)

```yaml
# pubspec.yaml
dependencies:
  flutter_client_sse: ^0.3.0
  # OR just use http and parse manually:
  http: ^1.2.0
```

```dart
import 'package:flutter_client_sse/flutter_client_sse.dart';
import 'dart:convert';

Stream<String> streamChat(String message, String baseUrl) async* {
  final url = '$baseUrl/api/chat/stream?message=${Uri.encodeComponent(message)}';

  final stream = SSEClient.subscribeToSSE(
    method: SSERequestType.GET,
    url: url,
    header: {'Accept': 'text/event-stream'},
  );

  await for (final event in stream) {
    if (event.event == 'done') break;
    if (event.event == 'token') {
      final data = jsonDecode(event.data ?? '{}');
      yield data['text'] as String;
    }
  }
}
```

**Manual approach** (no extra dependency — recommended for more control):

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';

Stream<Map<String, dynamic>> streamChat(String message, String baseUrl) async* {
  final request = http.Request(
    'GET',
    Uri.parse('$baseUrl/api/chat/stream?message=${Uri.encodeComponent(message)}'),
  );
  request.headers['Accept'] = 'text/event-stream';

  final response = await http.Client().send(request);
  final lines = response.stream
      .transform(utf8.decoder)
      .transform(const LineSplitter());

  String? currentEvent;
  StringBuffer dataBuffer = StringBuffer();

  await for (final line in lines) {
    if (line.startsWith('event:')) {
      currentEvent = line.substring(6).trim();
    } else if (line.startsWith('data:')) {
      dataBuffer.write(line.substring(5).trim());
    } else if (line.isEmpty && dataBuffer.isNotEmpty) {
      // Empty line = end of SSE message
      final parsed = jsonDecode(dataBuffer.toString());
      yield {'event': currentEvent, ...parsed};
      if (currentEvent == 'done') return;
      dataBuffer.clear();
      currentEvent = null;
    }
  }
}
```

## 5. POST-Based SSE (Better for Long Messages)

GET has URL length limits. For production, use POST:

```python
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

@app.post("/api/chat/stream")
async def stream_chat_post(request: Request, body: ChatRequest):
    async def event_stream():
        async for chunk in adk_event_generator(runner, "user-1", body.session_id, body.message):
            if await request.is_disconnected():
                break
            yield chunk

    return EventSourceResponse(event_stream())
```

Flutter side — POST-based SSE requires manual handling since `EventSource` is GET-only:

```dart
final request = http.Request('POST', Uri.parse('$baseUrl/api/chat/stream'));
request.headers['Content-Type'] = 'application/json';
request.headers['Accept'] = 'text/event-stream';
request.body = jsonEncode({'message': message, 'session_id': sessionId});
final response = await http.Client().send(request);
// Parse SSE from response.stream same as above
```

## 6. Recommendations for Ambient

| Decision | Recommendation |
|---|---|
| **SSE library (server)** | `sse-starlette>=2.0.0` — battle-tested with FastAPI |
| **SSE parsing (Flutter)** | Manual with `http` package — no extra dep, full control |
| **HTTP method** | POST for chat, GET for status/health streams |
| **Reconnection** | Client sends `Last-Event-ID` header; server includes `id:` field in each SSE message |
| **Heartbeat** | Server sends `event: ping` every 15s to keep connection alive through proxies |
| **Disconnect detection** | `request.is_disconnected()` check in the generator loop |
| **Buffering** | Set `X-Accel-Buffering: no` header (nginx) and `Cache-Control: no-cache` |

---

### Research: xtts_v2_setup (2026-03-26)
# XTTS v2 — Persistent FastAPI Service Guide

## 1. Installation

```bash
# Python 3.10+ required; 3.11 recommended
pip install TTS==0.22.0 fastapi uvicorn python-multipart torch torchaudio

# Or pin CUDA 12.1 wheels for deterministic GPU builds
pip install torch==2.3.1+cu121 torchaudio==2.3.1+cu121 \
  --index-url https://download.pytorch.org/whl/cu121
pip install TTS==0.22.0 fastapi uvicorn python-multipart
```

**First run** downloads the XTTS v2 checkpoint (~1.8 GB) to `~/.local/share/tts/`. Pre-download with:

```bash
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

---

## 2. FastAPI Server (`xtts_server.py`)

```python
import io, time, logging
from pathlib import Path
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

log = logging.getLogger("xtts")

# ── Model singleton ──────────────────────────────────────────────
MODEL: Xtts | None = None
SPEAKER_LATENTS: dict[str, tuple] = {}  # voice_name → (gpt_cond, speaker_emb)
VOICE_DIR = Path("voices")              # put .wav samples here

def load_model() -> Xtts:
    config = XttsConfig()
    config.load_json(str(Path.home() / ".local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2/config.json"))
    model = Xtts.init_from_config(config)
    model.load_checkpoint(
        config,
        checkpoint_dir=str(Path.home() / ".local/share/tts/tts_models--multilingual--multi-dataset--xtts_v2"),
        use_deepspeed=False,   # set True if deepspeed installed + multi-GPU
    )
    model.cuda()
    return model

def cache_voice(name: str, wav_path: Path):
    """Pre-compute speaker latents once per voice."""
    gpt_cond, speaker_emb = MODEL.get_conditioning_latents(
        audio_path=[str(wav_path)],
        gpt_cond_len=30,       # seconds of reference audio to use (max 30)
        gpt_cond_chunk_len=4,
    )
    SPEAKER_LATENTS[name] = (gpt_cond, speaker_emb)
    log.info(f"Cached voice '{name}' from {wav_path}")

# ── App lifecycle ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global MODEL
    MODEL = load_model()
    # Pre-cache every .wav in voices/
    VOICE_DIR.mkdir(exist_ok=True)
    for wav in VOICE_DIR.glob("*.wav"):
        cache_voice(wav.stem, wav)
    if not SPEAKER_LATENTS:
        log.warning("No voice samples in voices/ — upload one via POST /voices")
    yield

app = FastAPI(title="XTTS v2 TTS", lifespan=lifespan)

# ── Routes ────────────────────────────────────────────────────────
@app.post("/voices/{name}")
async def upload_voice(name: str, file: bytes = None):
    """Upload a .wav reference sample (6-30s, single speaker, clean audio)."""
    from fastapi import File, UploadFile
    # simplified — in production accept UploadFile
    path = VOICE_DIR / f"{name}.wav"
    path.write_bytes(file)
    cache_voice(name, path)
    return {"status": "ok", "voice": name}

@app.get("/tts")
def synthesize(
    text: str = Query(..., max_length=500),
    voice: str = Query("default"),
    language: str = Query("en"),
):
    if voice not in SPEAKER_LATENTS:
        raise HTTPException(404, f"Voice '{voice}' not found. Available: {list(SPEAKER_LATENTS)}")

    gpt_cond, speaker_emb = SPEAKER_LATENTS[voice]

    t0 = time.perf_counter()
    out = MODEL.inference(
        text=text,
        language=language,
        gpt_cond_latent=gpt_cond,
        speaker_embedding=speaker_emb,
        temperature=0.65,
        repetition_penalty=5.0,
        top_k=50,
        top_p=0.85,
        enable_text_splitting=True,  # auto-splits long text into sentences
    )
    elapsed = time.perf_counter() - t0
    log.info(f"Generated {len(out['wav'])/ 24000:.1f}s audio in {elapsed:.2f}s")

    # Encode to WAV in-memory
    import torchaudio
    buf = io.BytesIO()
    torchaudio.save(buf, torch.tensor(out["wav"]).unsqueeze(0), 24000, format="wav")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="audio/wav",
        headers={"X-Inference-Time": f"{elapsed:.3f}"},
    )

@app.get("/voices")
def list_voices():
    return {"voices": list(SPEAKER_LATENTS.keys())}
```

**Run:**

```bash
uvicorn xtts_server:app --host 0.0.0.0 --port 8200 --workers 1
# workers=1 is mandatory — the model is not fork-safe
```

---

## 3. Voice Cloning Setup

Place a reference WAV in `voices/`:

| Parameter | Recommendation |
|---|---|
| Duration | 6–30 seconds (longer = better quality, diminishing returns past 20s) |
| Format | 16-bit PCM WAV, mono, 22050 or 24000 Hz |
| Content | Natural speech, single speaker, no background noise or music |
| Normalization | Peak-normalize to -1 dB; avoid clipping |

```bash
# Quick prep with ffmpeg
ffmpeg -i raw_sample.mp3 -ac 1 -ar 24000 -acodec pcm_s16le voices/chieh.wav
```

The server caches speaker latents at startup. Adding a new voice at runtime:

```bash
curl -X POST http://localhost:8200/voices/chieh \
  --data-binary @voices/chieh.wav
```

---

## 4. Expected Latency (GPU)

Benchmarked on single sentences (~10-20 words). VRAM shown is runtime usage with model loaded.

| GPU | VRAM | First-token | Full sentence (15 words) | RTF |
|---|---|---|---|---|
| RTX 3060 12GB | ~4.2 GB | ~180 ms | **0.8–1.2s** | 0.15–0.22× |
| RTX 3090 24GB | ~4.2 GB | ~120 ms | **0.5–0.7s** | 0.08–0.12× |
| RTX 4090 24GB | ~4.2 GB | ~80 ms | **0.3–0.5s** | 0.05–0.08× |
| T4 16GB | ~4.2 GB | ~250 ms | **1.2–1.8s** | 0.25–0.35× |

**RTF** = Real-Time Factor (lower = faster than real-time). A 15-word sentence produces ~3s of audio.

**CPU fallback**: 8–15× slower. Not recommended for interactive use.

**Optimization levers:**
- `use_deepspeed=True` — 15-20% speedup on multi-GPU or large-VRAM cards
- `torch.compile(model)` (PyTorch 2.x) — marginal gains, long warmup
- Sentence splitting + parallel inference — useful for paragraphs, not single sentences

---

## 5. Python Client

```python
import httpx

XTTS_URL = "http://localhost:8200"

def speak(text: str, voice: str = "default", language: str = "en") -> bytes:
    """Returns raw WAV bytes. Raises on error."""
    resp = httpx.get(
        f"{XTTS_URL}/tts",
        params={"text": text, "voice": voice, "language": language},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.content

# ── Usage ──
wav = speak("Hello Chieh, the backup completed successfully.", voice="chieh")

# Play directly (Linux)
import subprocess, tempfile, os
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
    f.write(wav)
    f.flush()
    subprocess.run(["aplay", f.name])
    os.unlink(f.name)
```

**Async variant** (for FastAPI integration):

```python
async def speak_async(text: str, voice: str = "default") -> bytes:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{XTTS_URL}/tts",
            params={"text": text, "voice": voice},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.content
```

---

## 6. systemd Unit (Production)

```ini
# /etc/systemd/system/xtts.service
[Unit]
Description=XTTS v2 TTS Server
After=network.target

[Service]
Type=simple
User=chieh
WorkingDirectory=/home/chieh/ambient/vessence
ExecStart=/home/chieh/ambient/vessence/.venv/bin/uvicorn xtts_server:app --host 127.0.0.1 --port 8200 --workers 1
Restart=on-failure
RestartSec=5
Environment=CUDA_VISIBLE_DEVICES=0

[Install]
WantedBy=multi-user.target
```

---

## 7. Integration Notes for Ambient/Jane

- **Endpoint**: Jane's TTS route (`POST /api/tts/generate` in `main.py:L697`) should proxy to this service rather than running inference in-process. Keeps the web server responsive.
- **Voice management**: Store voice samples in `vault/voices/` and symlink or copy to the XTTS `voices/` directory. One voice per essence is a natural mapping.
- **Latency budget**: For interactive chat, target < 1.5s end-to-end (inference + network + playback start). On a 3060 or better this is achievable for single sentences.
- **Streaming**: XTTS v2 does not natively support chunk-by-chunk audio streaming. For perceived low-latency, split long responses into sentences server-side (`enable_text_splitting=True`) and stream each sentence's audio as it completes.

---

### Research: f5_tts_comparison (2026-03-26)
# F5-TTS vs XTTS v2 — Technical Comparison for Personal Voice Assistant

## Head-to-Head

| Criterion | F5-TTS (`SWivid/F5-TTS`) | XTTS v2 (`coqui-ai/TTS`) | Winner |
|---|---|---|---|
| **Naturalness** | MOS ~4.0–4.2, flow-matching DiT; expressive prosody | MOS ~3.8–4.0, autoregressive+VITS; occasionally robotic on long utterances | **F5-TTS** |
| **GPU Latency** (10s audio, RTX 3060) | 4–8s (16-32 steps); turbo variant 2–4s (6-8 steps). No native streaming | 2–5s total; **native streaming** with ~500ms–1.5s first-chunk latency | **XTTS v2** (streaming) |
| **Setup** | `pip install f5-tts`, Python 3.10+, clean deps, Gradio UI included | `pip install TTS`, Python 3.9–3.11, heavy deps. Stale pins since Coqui bankruptcy | **F5-TTS** |
| **Voice Cloning** | Zero-shot from ~3s clip (10–15s recommended). Excellent speaker similarity | Zero-shot from ~6s clip (15–30s recommended). Good similarity, 17 languages | **F5-TTS** (quality) / **XTTS** (language breadth) |
| **Maintenance** | ~12–15k stars, actively maintained, regular commits | ~35k stars (legacy). **Coqui shut down Nov 2023.** Idiap fork (`idiap/coqui-ai-TTS`) has bug fixes only | **F5-TTS** |
| **License** | Code: MIT. Weights: some CC-BY-NC-4.0 — check model card | Code: MPL-2.0. Weights: Coqui Public Model License (commercial OK with attribution) | Roughly even |

## Recommendation

**Use F5-TTS.** It wins on naturalness, cloning quality, setup, and maintenance. XTTS v2 is effectively abandonware.

If **streaming latency** is a hard requirement, consider **Fish Speech v1.4+** instead — it has native streaming (~500ms first chunk), Apache 2.0 license, and quality close to F5-TTS:

```bash
pip install fish-speech   # fishaudio/fish-speech
```

## Newer Alternatives Worth Knowing

| Model | Best For | Caveat |
|---|---|---|
| **Fish Speech 1.4+** | Streaming + multilingual + cloning | English naturalness slightly below F5-TTS |
| **Kokoro** (Hexgrad) | Ultra-fast (82M params), CPU-viable | Style-based voices, not reference-audio cloning |
| **MeloTTS** (MyShell) | Real-time on CPU, dead simple | Weak voice cloning |
| **Dia** (Nari Labs) | Multi-speaker dialogue with non-verbal sounds | Newer, less proven for single-speaker |
| **StyleTTS2** | Top-tier naturalness (MOS ~4.1+) | Cloning setup is manual, less actively maintained |

## For Ambient Specifically

Given the project runs a local server with GPU access and needs a cloned personal voice:

- **Primary:** F5-TTS turbo (6-8 flow steps) — gives 2-4s generation for 10s audio
- **Fallback:** Fish Speech if you later need true token-by-token streaming to the Flutter client
- **Reference clip:** Record 10-15 seconds of clean speech for the voice you want to clone
- **VRAM:** Either model fits in ~3-4 GB, leaving headroom for Gemma on the same GPU

---

### Research: faster_whisper_vad (2026-03-26)
# Real-Time STT Pipeline: faster-whisper + silero-vad

## Package Versions

```
faster-whisper>=1.1.0
silero-vad>=5.1
sounddevice>=0.5.1
numpy>=1.26
```

## Architecture

```
Mic (16kHz mono) → Ring Buffer → Silero VAD → Speech Segments → faster-whisper → Text
                                  ↓
                          start/end detection
                          with padding + timeout
```

## 1. VAD Setup

```python
import torch
import numpy as np

# Load Silero VAD (ONNX version for lower latency)
model, utils = torch.hub.load(
    repo_or_dir="snakers4/silero-vad",
    model="silero_vad",
    onnx=True,
)
(get_speech_timestamps, _, read_audio, _, _) = utils

# VAD operates on 512-sample chunks at 16kHz (32ms frames)
VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SAMPLES = 512  # 32ms — required by silero for 16kHz
SPEECH_PAD_MS = 300       # padding around detected speech
MIN_SPEECH_MS = 250       # ignore segments shorter than this
SILENCE_TIMEOUT_MS = 700  # end-of-utterance after this much silence
```

## 2. Streaming Microphone Capture + VAD Gate

```python
import sounddevice as sd
import collections
import threading
import time

class VoiceActivityDetector:
    """Streams mic audio, emits complete utterances via callback."""

    def __init__(self, on_utterance: callable):
        self.on_utterance = on_utterance
        self.sample_rate = VAD_SAMPLE_RATE
        self._ring = collections.deque(maxlen=int(self.sample_rate * 30))  # 30s max
        self._is_speaking = False
        self._silence_start: float | None = None
        self._speech_buffer: list[np.ndarray] = []
        self._lock = threading.Lock()

    def start(self):
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=VAD_CHUNK_SAMPLES,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self):
        self._stream.stop()
        self._stream.close()

    def _audio_callback(self, indata: np.ndarray, frames, time_info, status):
        chunk = indata[:, 0].copy()  # mono float32

        # Silero expects a 1-D torch tensor
        tensor = torch.from_numpy(chunk)
        speech_prob = model(tensor, self.sample_rate).item()

        with self._lock:
            if speech_prob >= 0.5:
                # Speech detected
                self._silence_start = None
                if not self._is_speaking:
                    self._is_speaking = True
                    # Prepend ~300ms of pre-speech audio for context
                    pad_samples = int(self.sample_rate * SPEECH_PAD_MS / 1000)
                    pre_audio = list(self._ring)[-pad_samples:]
                    if pre_audio:
                        self._speech_buffer.append(np.concatenate(pre_audio) 
                                                   if len(pre_audio) > 1 
                                                   else pre_audio[0])
                self._speech_buffer.append(chunk)

            elif self._is_speaking:
                # Silence while speaking — track timeout
                self._speech_buffer.append(chunk)
                if self._silence_start is None:
                    self._silence_start = time.monotonic()
                elif (time.monotonic() - self._silence_start) * 1000 > SILENCE_TIMEOUT_MS:
                    self._finalize_utterance()

            # Always push to ring buffer for pre-speech padding
            self._ring.append(chunk)

    def _finalize_utterance(self):
        audio = np.concatenate(self._speech_buffer)
        self._speech_buffer.clear()
        self._is_speaking = False
        self._silence_start = None

        duration_ms = len(audio) / self.sample_rate * 1000
        if duration_ms >= MIN_SPEECH_MS:
            # Fire in background so we don't block the audio thread
            threading.Thread(
                target=self.on_utterance,
                args=(audio,),
                daemon=True,
            ).start()
```

## 3. Whisper Transcription

```python
from faster_whisper import WhisperModel

# Model selection for low latency:
#   - "tiny.en"    ~39MB, ~10x RT on CPU    — lowest latency, fine for commands
#   - "base.en"    ~74MB, ~7x RT on CPU     — good balance
#   - "small.en"   ~244MB, ~4x RT on CPU    — best accuracy/speed tradeoff
#   - "medium.en"  ~769MB, ~2x RT on CPU    — use if GPU available
#   - "large-v3"   ~1.5GB, GPU recommended  — best accuracy
#
# For Ambient (local, low-latency, English):
#   CPU-only → "base.en" with int8 quantization
#   GPU      → "small.en" with float16

whisper = WhisperModel(
    "base.en",
    device="cpu",           # or "cuda"
    compute_type="int8",    # "float16" for GPU
    cpu_threads=4,
    num_workers=1,
)

def transcribe_utterance(audio: np.ndarray):
    """Called by VAD when a complete utterance is detected."""
    segments, info = whisper.transcribe(
        audio,
        beam_size=1,              # greedy decoding — fastest
        best_of=1,
        temperature=0.0,
        language="en",
        condition_on_previous_text=False,  # each utterance is independent
        vad_filter=False,         # we already ran VAD
        without_timestamps=True,  # skip timestamp alignment — saves ~15%
    )

    text = " ".join(seg.text.strip() for seg in segments).strip()
    if text:
        handle_stt_result(text, info.language_probability)
```

## 4. Putting It Together

```python
def handle_stt_result(text: str, confidence: float):
    """Send transcribed text to Amber / the app."""
    print(f"[STT] ({confidence:.0%}) {text}")
    # → push to your FastAPI websocket, event bus, etc.

def main():
    vad = VoiceActivityDetector(on_utterance=transcribe_utterance)
    vad.start()
    print("Listening... (Ctrl+C to stop)")
    try:
        threading.Event().wait()  # block forever
    except KeyboardInterrupt:
        vad.stop()
```

## 5. Tuning Knobs

| Parameter | Effect | Recommended |
|---|---|---|
| `SILENCE_TIMEOUT_MS` | How long silence before utterance ends | 500-800ms (700 default) |
| `MIN_SPEECH_MS` | Discard short noise bursts | 200-300ms |
| `SPEECH_PAD_MS` | Pre-speech audio included | 200-400ms |
| `beam_size` | Whisper search width | 1 (greedy) for speed, 5 for accuracy |
| `VAD threshold` | `speech_prob >= X` | 0.5 default, raise to 0.6 if noisy env |

## 6. Latency Budget (CPU, base.en, int8)

| Stage | Time |
|---|---|
| VAD decision | ~2ms per 32ms frame |
| Silence timeout | 700ms (configurable) |
| Whisper transcribe (3s utterance) | ~400ms |
| **Total end-to-end** | **~1.1s after user stops speaking** |

## Key Design Decisions for Ambient

1. **Keep VAD and Whisper on separate threads** — VAD must never block the audio callback or you'll get buffer overruns.
2. **Use `condition_on_previous_text=False`** — each utterance is independent in a voice assistant context; setting this to `True` causes hallucination loops on silence.
3. **Pre-load the model at startup** — first inference has a ~2s warm-up; call `whisper.transcribe(np.zeros(16000, dtype=np.float32))` during init.
4. **ONNX silero** — the ONNX runtime path avoids PyTorch overhead for VAD inference (~2ms vs ~8ms per frame).
5. **For Android**: faster-whisper is CPython-only. On Android, use `whisper.cpp` via FFI from Kotlin/Flutter instead, with the same VAD logic ported to the `webrtcvad` or `silero` ONNX model via `onnxruntime-android`.

---

### Research: tailscale_self_hosted (2026-03-26)
> **Note:** Your existing architecture decision (2026-03-21) already chose a custom relay server at `relay.vessences.com` over Tailscale/Cloudflare, specifically so users don't need any networking setup. The answer below is still useful if you want Tailscale as a developer/power-user option or if you revisit that decision.

---

# Tailscale / Headscale for Secure Home Server Access

## 1. Tailscale (Managed Coordination Server)

### Home Linux Server

```bash
# Install
curl -fsSL https://tailscale.com/install.sh | sh

# Start and authenticate
sudo tailscale up --advertise-exit-node   # optional: act as exit node
sudo tailscale status                      # shows MagicDNS hostname + 100.x.y.z IP
```

The server gets a stable IP like `100.64.0.1` and a MagicDNS name like `homeserver.tail1234.ts.net`.

### Android Device

Install **Tailscale** from Play Store → sign in with same account → done. The device gets its own `100.x.y.z` IP and can reach the server at its Tailscale IP or MagicDNS name.

### Windows Laptop

Install Tailscale from `tailscale.com/download/windows` → sign in → same story.

### Key Config (Tailscale Admin Console)

| Setting | Recommendation |
|---|---|
| **ACLs** | Restrict so only your devices can reach the server's port (e.g., `8081` for the ADK API) |
| **MagicDNS** | Enable — lets you use `homeserver.tail1234.ts.net` instead of raw IPs |
| **Key expiry** | Disable for the server node (so it doesn't drop off the network) |
| **HTTPS certs** | `tailscale cert homeserver.tail1234.ts.net` — gives you a real Let's Encrypt cert for the Tailscale domain |

---

## 2. Headscale (Fully Self-Hosted)

Replaces Tailscale's coordination server. You run it yourself — zero dependency on Tailscale Inc.

```bash
# On a small VPS or the home server itself
docker run -d \
  --name headscale \
  -v /etc/headscale:/etc/headscale \
  -p 8080:8080 \
  -p 443:443 \
  headscale/headscale:0.23 \
  serve

# Create a user
docker exec headscale headscale users create chieh

# Generate a pre-auth key
docker exec headscale headscale preauthkeys create --user chieh --reusable --expiration 365d
```

Then on each client:

```bash
# Linux server
sudo tailscale up --login-server https://your-headscale-domain:443 --authkey <key>

# Android: use the Tailscale app's "Change server" (3-dot menu) to point at your Headscale URL
# Windows: same Tailscale client, same --login-server flag
```

**Trade-off:** Headscale gives you full control but you maintain the coordination server yourself. Tailscale's free tier (3 users, 100 devices) is usually sufficient for personal use.

---

## 3. Flutter App Handling

**The good news: your Flutter app needs almost nothing special.**

Tailscale operates at the OS network layer (WireGuard tunnel). Once Tailscale is connected on the device, `100.x.y.z` addresses are routable like any LAN IP. Your app just makes normal HTTP requests.

### What to do in the app

```dart
// Store the server address as a user-configurable setting
// Default to LAN IP, user can switch to Tailscale IP or MagicDNS name
class ServerConfig {
  // Examples of what the user might enter:
  //   LAN:       192.168.1.50:8081
  //   Tailscale: 100.64.0.1:8081
  //   MagicDNS:  homeserver.tail1234.ts.net:8081
  String serverAddress;
}
```

### Checklist

| Concern | Answer |
|---|---|
| **Special permissions?** | No. Tailscale runs as a VPN service at the OS level. The app just sees a normal network route. |
| **Android `usesCleartextTraffic`?** | If using Tailscale HTTPS certs, no. If using plain HTTP over Tailscale, yes — add `android:usesCleartextTraffic="true"` in `AndroidManifest.xml` or a network security config. |
| **Connection timeouts** | Tailscale's first connection after device wake can take 1-3s for DERP relay negotiation. Use a generous initial timeout (~10s) and show a "connecting..." state. |
| **Detecting Tailscale availability** | Don't. Just try to connect. If it fails, show "Can't reach server — check your network or Tailscale connection." The app shouldn't care *how* the network works. |
| **MagicDNS resolution** | Works automatically on all platforms once Tailscale is running. No special DNS config in Flutter. |

### Network security config (Android, if using HTTP)

```xml
<!-- android/app/src/main/res/xml/network_security_config.xml -->
<network-security-config>
  <domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="true">100.64.0.0/10</domain>
  </domain-config>
</network-security-config>
```

---

## 4. Recommendation

Given your existing relay architecture:

- **For end users** — keep the relay. Zero setup is the right call.
- **For you (dev/admin)** — Tailscale free tier is worth running alongside the relay. It gives you direct, low-latency SSH and API access to the home server from anywhere without exposing ports. Takes 5 minutes to set up and doesn't conflict with the relay.
- **Headscale** — only worth it if you have a philosophical objection to Tailscale's coordination server seeing your device metadata. Functionally identical, more maintenance.