# Job: Deep audit of Vessence operation for Android/Web Jane response speed
Status: completed
Priority: 1
Created: 2026-03-27

## Objective
Perform a deep audit of the Vessence runtime and identify the 5 highest-impact improvements to reduce response latency for Jane on Android and web.

## Context
The user wants a high-value latency audit, not a shallow list of generic ideas. The goal is to inspect the real Vessence request path end to end and surface the changes with the best expected payoff for user-perceived speed.

This audit must focus on the live Jane stack used by web and Android, including:
- request intake and SSE streaming
- intent classification and routing
- context building and prompt shaping
- memory retrieval and librarian/bypass paths
- standing brain execution and process reuse
- frontend display timing, buffering, and completion handling
- any duplicate work, blocking I/O, or token waste that materially slows responses

Relevant architecture and prior work already mention:
- standing brain process tiers in `jane/standing_brain.py`
- request orchestration in `jane_web/jane_proxy.py`
- streaming endpoints in `jane_web/main.py`
- prompt shaping and context assembly in `jane/context_builder.py`
- memory retrieval in `memory_retrieval.py`
- Android and web chat UIs consuming Jane SSE events
- prior optimizations like context builder caching, memory prefetch, intent classifier routing, async persistence, and static asset caching

The audit should not assume existing optimizations are still correct or high-leverage. Re-measure the live path and look for current bottlenecks.

## Pre-conditions
1. Use the live Vessence roots:
   - code: `/home/chieh/ambient/vessence`
   - data: `/home/chieh/ambient/vessence-data`
   - vault: `/home/chieh/ambient/vault`
2. Read the current architecture and accomplishment docs before auditing.
3. Use logs, timings, and source inspection before proposing fixes.

## Steps
1. Map the full request path for Jane on web and Android from user submit to first visible token and final completion.
2. Inspect current timing and runtime logs to identify where time is being spent:
   - request timing logs
   - Jane web logs
   - standing brain behavior
   - memory retrieval and prompt dump artifacts
3. Separate latency into at least these buckets where possible:
   - classification
   - context building
   - memory retrieval
   - brain queue/wait time
   - first-token generation
   - stream/render delay
   - post-response cleanup that may still block
4. Identify real token waste or duplicated work in the request path that still affects latency.
5. Produce exactly 5 improvements, ordered by expected impact, each with:
   - root cause
   - proposed change
   - estimated latency benefit
   - implementation risk/complexity
   - files/components affected
6. Prefer improvements that materially help both Android and web Jane, or clearly explain if an item is platform-specific.
7. If one or more of the top 5 improvements are quick wins, note that explicitly.

## Verification
1. Provide a written audit with exactly 5 ranked improvements.
2. For each recommendation, cite the concrete evidence from logs, code paths, or measurements that support it.
3. Make clear whether the bottleneck affects:
   - time to first visible output
   - total completion time
   - both
4. Ensure the recommendations are specific enough that a follow-up implementation job can be created directly from the audit.

## Files Involved
- `jane_web/jane_proxy.py`
- `jane_web/main.py`
- `jane/context_builder.py`
- `jane/standing_brain.py`
- `memory_retrieval.py`
- `agent_skills/conversation_manager.py`
- Android Jane client files that consume Jane streaming events
- `/home/chieh/ambient/vessence-data/logs/`

## Notes
- Focus on present-day bottlenecks, not historical ones that may already be fixed.
- Prior audits and speed work exist, but this job should verify the current state independently.
- The output should help decide the next 1-2 implementation jobs with the best speed payoff.

## Result

### Evidence Summary
- Live timing data from `/home/chieh/ambient/vessence-data/logs/jane_request_timing.log` shows the dominant latency is still model execution, not prompt assembly:
  - `brain_execute`: count 501, avg 49.2s, p50 26.2s, p90 132.0s, p95 168.8s, max 333.0s
  - `request_total`: count 506, avg 52.5s, p50 28.7s, p90 138.4s, p95 173.5s, max 433.6s
  - `context_build`: count 753, avg 0.8s, p50 0ms, p90 435ms, p95 2.2s, but worst outliers hit 100.5s
- `brain_execute` duration buckets:
  - 0-10s: 127 requests
  - 10-30s: 149 requests
  - 30-60s: 89 requests
  - 60-120s: 75 requests
  - 120s+: 61 requests
- Recent live requests on March 27, 2026 include `brain_execute` times of 13.6s, 15.9s, 17.6s, 24.7s, 53.3s, and 122.3s, all while using `claude-opus-4-6`.
- Non-brain overhead is usually much smaller but still material for first visible feedback: estimated `request_total - brain_execute` has p50 1.4s, p90 23.7s, p95 61.5s.
- Warm-turn prompt dumps show prompt growth on resumed turns even with `system_prompt_chars=0`: recent `transcript_chars` include 1140, 1169, 1184, 1420, and 1594 for short user messages. Historical max in prompt dumps is 51,286 transcript chars.
- Cold-turn prompt dumps still show very large system prompts for small messages: 4,164 chars for an 81-char message, and 7,008 chars for a 5-char message.
- Auxiliary request load is non-trivial:
  - Web polls `/api/jane/announcements` every 15s and `/health` every 15s.
  - Android polls `/api/jane/announcements` every 5s and also holds `/api/jane/live` SSE.
  - `jane_web.log` shows repeated paired `/health` and announcement requests from connected clients while the system is otherwise busy.

### Top 5 Improvements

#### 1. Restore real model routing for web/Android Jane instead of effectively running everything through Opus
- Root cause:
  - The live path is behaving as a fixed heavy-brain system. Recent timing logs show sampled requests going through `brain=Claude`, and streamed status lines show `Jane is thinking (claude-opus-4-6)...`.
  - `jane_web/jane_proxy.py` always passes `WEB_CHAT_MODEL` into the persistent Claude path, while `jane/standing_brain.py` exposes a single provider model rather than the documented light/medium/heavy routing.
- Why this is the highest impact:
  - `brain_execute` is the dominant cost by far: p50 26.2s and p90 132.0s.
  - Many short prompts are paying Opus latency even when they do not need Opus-level reasoning.
- Proposed change:
  - Reconnect live intent classification to actual model selection for web and Android.
  - Route greeting/simple turns to Haiku or an equivalent light tier, medium turns to Sonnet, and reserve Opus for genuinely hard/tool-heavy turns.
  - Make the standing brain truly multi-tier again, or bypass it for light/medium turns if that is simpler.
- Estimated benefit:
  - Largest backend win in the system. Expect major reductions in both time-to-first-token and total response time for the majority of turns.
- Risk/complexity:
  - Medium. Requires aligning current standing-brain behavior, persistent Claude sessions, and the documented routing model.
- Files/components affected:
  - `jane_web/jane_proxy.py`
  - `jane/standing_brain.py`
  - `jane/brain_adapters.py`
  - `jane/config.py`

#### 2. Flush status events before context build finishes so web and Android stop sitting silent on cold turns
- Root cause:
  - In `jane_web/jane_proxy.py`, `stream_message()` queues `start` and early `status` events immediately, but does not begin draining that queue to the client until after context build completes.
  - That means the UI cannot display “Reviewing the current thread...” or “Loading memory...” while the backend is still building context.
- Evidence:
  - `context_build` is usually small, but the p95 is still 2.2s and outliers reach 15.9s, 64.6s, 99.7s, and 100.5s.
  - This directly harms perceived responsiveness even when the eventual answer is fast.
- Proposed change:
  - Start yielding queued SSE events immediately after `emit("start")`, while context build runs in a background task.
  - Treat “first visible status” as a first-class latency target, not just final response latency.
- Estimated benefit:
  - Large improvement to perceived speed on both web and Android, especially first-turn and cold-turn interactions.
- Risk/complexity:
  - Low to medium. Mostly a stream-control refactor.
- Files/components affected:
  - `jane_web/jane_proxy.py`
  - `jane_web/main.py`
  - Web and Android chat UIs consuming the stream

#### 3. Stop re-sending large “recent history” transcripts on warm standing-brain turns
- Root cause:
  - The standing-brain fast path skips system prompt rebuild, but still sends `[Recent exchanges]` plus the user message on resumed turns.
  - In `stream_message()`, warm turns use `brain_message = request_ctx.transcript`, not just the latest user message.
- Evidence:
  - Recent warm turns show `system_prompt_chars=0` but `transcript_chars` of 1140, 1169, 1184, 1420, and 1594 for short follow-ups.
  - Prompt dump max transcript size is 51,286 chars.
  - This is duplicated context sent to a process that already remembers the session.
- Proposed change:
  - Default warm turns to “latest user message only”.
  - Inject minimal repair context only for clearly anaphoric follow-ups, after model rotation, or after explicit recovery.
  - Add a hard cap on resumed-turn transcript size.
- Estimated benefit:
  - Strong reduction in token load and model latency on multi-turn chats, which are the common Android/web path.
- Risk/complexity:
  - Medium. Needs care around pronoun resolution and post-rotation continuity.
- Files/components affected:
  - `jane_web/jane_proxy.py`
  - `jane/context_builder.py`
  - `jane/standing_brain.py`
  - `jane/persistent_claude.py`

#### 4. Harden cold-start context retrieval with a strict memory/prewarm circuit breaker and actual first-turn reuse
- Root cause:
  - Prewarm and memory bootstrap exist, but they are still best-effort and occasionally pathological.
  - `session_prewarm` has severe outliers: p90 7.7s, p95 9.3s, max 711.6s.
  - `context_build` also has extreme outliers despite tiny user messages, which points to retrieval/bootstrap stalls.
  - `_safe_get_memory_summary()` still has a blocking HTTP timeout path before fallback.
- Proposed change:
  - Add a hard latency budget for prewarm and memory bootstrap.
  - If the memory daemon is slow or unavailable, skip directly to fallback summary instead of waiting the full timeout budget.
  - Persist and reuse bootstrap memory more aggressively on the first real turn.
  - Record per-substep timings inside context build so stalls are attributable.
- Estimated benefit:
  - High impact on cold turns and startup experience, and it will remove the worst tail-latency spikes.
- Risk/complexity:
  - Medium. Mostly control-flow hardening and instrumentation.
- Files/components affected:
  - `jane_web/jane_proxy.py`
  - `jane/context_builder.py`
  - memory daemon integration at `startup_code/memory_daemon.py`

#### 5. Replace aggressive announcement/health polling with push or adaptive backoff
- Root cause:
  - Web polls announcements every 15s and health every 15s from `vault_web/templates/jane.html`.
  - Android polls announcements every 5s in `AnnouncementPoller.kt` while also maintaining a live SSE connection in `LiveBroadcastListener.kt`.
  - These background requests continue during active chat sessions and add avoidable server work.
- Evidence:
  - `jane_web.log` shows repeated paired `/health` and `/api/jane/announcements` requests from connected clients while the system is otherwise idle or busy with chat.
  - This is not the biggest single latency cause, but it is constant load on the same service process that must also stream Jane responses.
- Proposed change:
  - Push announcements over the existing SSE path or a unified lightweight stream.
  - Back off health checks aggressively when the user is active and the stream is already healthy.
  - For Android, reduce announcement polling frequency or suspend it while SSE is connected.
- Estimated benefit:
  - Moderate but broad. Helps tail latency and system headroom, especially on weaker hosts or when multiple clients are connected.
- Risk/complexity:
  - Low to medium.
- Files/components affected:
  - `vault_web/templates/jane.html`
  - `android/app/src/main/java/com/vessences/android/data/repository/AnnouncementPoller.kt`
  - `android/app/src/main/java/com/vessences/android/data/repository/LiveBroadcastListener.kt`
  - `jane_web/main.py`

### Recommended Next Jobs
1. Re-enable real model routing for Jane web/Android and verify the latency distribution before/after.
2. Refactor `stream_message()` so status events flush immediately during context build.

### Conclusion
The backend model path is still the main speed problem. The single largest win is to stop treating most Android/web turns as Opus turns. After that, the biggest user-visible win is to flush early stream events immediately, followed by cutting duplicated warm-turn transcript payload and hardening cold-start memory bootstrap.
