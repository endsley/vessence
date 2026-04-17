package com.vessences.android.tools

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import java.util.concurrent.ConcurrentLinkedDeque
import java.util.concurrent.atomic.AtomicInteger

/**
 * Central dispatcher for all [ClientToolCall] events arriving from the server
 * via the `client_tool_call` SSE event type.
 *
 * Responsibilities:
 *  - Parse the raw JSON payload.
 *  - Dedupe on `call_id` (both in-memory and persisted to SharedPreferences
 *    with a 5-minute TTL so SSE replay across app restarts does not double-fire).
 *  - Gate all dispatch behind the [Constants.PREF_PHONE_TOOLS_ENABLED] feature flag.
 *  - Look up the [ClientToolHandler] for the tool name and invoke it on
 *    [scope], awaiting its [ToolActionStatus].
 *  - Record the result in [PendingToolResultBuffer] so it rides on the next
 *    outgoing user message as a [TOOL_RESULT:{json}] prefix.
 *  - Expose the most recent status via [lastStatus] for UI observation
 *    (draft preview bubble, error banners, etc).
 *
 * Phase 1: dispatcher is wired up but the handler registry is EMPTY. Phase 2
 * (coming next) populates it with ContactsCallHandler, ContactsSmsHandler, and
 * MessagesReadRecentHandler.
 */
class ClientToolDispatcher(
    private val actionQueue: ActionQueue,
) {
    private val handlers: MutableMap<String, ClientToolHandler> = mutableMapOf()
    private val seenCallIds: ConcurrentLinkedDeque<SeenEntry> = ConcurrentLinkedDeque()
    private val dedupeLock = Any()  // guards isDuplicate/recordSeen atomicity
    private val gson = Gson()
    private val job: Job = SupervisorJob()
    private val scope = CoroutineScope(job + Dispatchers.Default)

    @Volatile
    private var persistentDedupePruned = false

    private val _lastStatus = MutableStateFlow<Pair<String, ToolActionStatus>?>(null)
    val lastStatus: StateFlow<Pair<String, ToolActionStatus>?> = _lastStatus

    init {
        register(ContactsCallHandler)
        register(ContactsSmsHandler)
        ContactsSmsHandler.ALIASES.forEach { alias ->
            registerAlias(alias, ContactsSmsHandler)
        }
        register(MessagesReadRecentHandler)
        register(MessagesFetchUnreadHandler)
        register(MessagesReadInboxHandler)
        register(SyncForceSmsHandler)
        register(DeviceSpeakTimeHandler)
        register(TimerHandler)
        TimerHandler.ALIASES.forEach { alias ->
            registerAlias(alias, TimerHandler)
        }
    }

    /** Register a handler under its [ClientToolHandler.name]. */
    fun register(handler: ClientToolHandler) {
        handlers[handler.name] = handler
    }

    /**
     * Register the same handler under additional aliases (same instance, many
     * tool names). Used by ContactsSmsHandler to handle all four
     * sms_draft/update/send/cancel sub-tools in a single class with shared state.
     */
    fun registerAlias(alias: String, handler: ClientToolHandler) {
        handlers[alias] = handler
    }

    /**
     * Parse a raw JSON payload (the `data` field of a `client_tool_call` SSE
     * event) and dispatch it. Feature-flag-gated: if phone tools are disabled
     * in preferences, the call is silently dropped.
     */
    fun dispatchRaw(rawJson: String, ctx: Context) {
        if (!isFeatureEnabled(ctx)) {
            Log.i(TAG, "phone tools disabled by feature flag — ignoring tool call")
            return
        }
        val call = parseCall(rawJson) ?: run {
            Log.w(TAG, "failed to parse tool call payload: ${rawJson.take(200)}")
            return
        }
        dispatch(call, ctx)
    }

    /** Invoke a handler for an already-parsed [ClientToolCall]. */
    fun dispatch(call: ClientToolCall, ctx: Context) {
        // Atomic dedupe: isDuplicate + recordSeen must not race. Wrap in a
        // synchronized block so two concurrent dispatches with the same
        // call_id cannot both pass the dedupe check.
        val now = System.currentTimeMillis()
        synchronized(dedupeLock) {
            pruneSeen(now)
            pruneSharedPrefsOnce(ctx, now)
            if (isDuplicate(call.callId, now, ctx)) {
                Log.i(TAG, "duplicate call_id ${call.callId}, skipping")
                return
            }
            recordSeen(call.callId, now, ctx)
        }

        val handler = handlers[call.tool]
        if (handler == null) {
            // Phase 1 scaffolding: any tool call without a registered handler
            // reports "unsupported" (not "failed") so Jane's mind knows this
            // is a client version/capability gap, not a real runtime error.
            Log.w(TAG, "no handler for tool '${call.tool}' — reporting unsupported")
            val unsupported = ToolActionStatus.Failed("unsupported on this client")
            _lastStatus.value = call.callId to unsupported
            PendingToolResultBuffer.record(
                ToolResult(
                    tool = call.tool,
                    callId = call.callId,
                    status = "unsupported",
                    message = "handler not registered on this Android client version",
                )
            )
            return
        }

        PendingToolResultBuffer.inFlightHandlers.incrementAndGet()
        scope.launch {
            val t0 = System.currentTimeMillis()
            reportHandlerDiagnostic(ctx, call.tool, call.callId, "started", "")
            try {
                _lastStatus.value = call.callId to ToolActionStatus.Requested
                val result: ToolActionStatus = try {
                    handler.handle(call, ctx, actionQueue)
                } catch (e: Exception) {
                    Log.e(TAG, "handler '${call.tool}' threw", e)
                    ToolActionStatus.Failed(e.message ?: e.javaClass.simpleName)
                }
                val elapsed = System.currentTimeMillis() - t0
                val statusName = when (result) {
                    is ToolActionStatus.Completed -> "completed"
                    is ToolActionStatus.CompletedWithData -> "completed_data"
                    is ToolActionStatus.Failed -> "failed"
                    is ToolActionStatus.Cancelled -> "cancelled"
                    is ToolActionStatus.NeedsUser -> "needs_user"
                    is ToolActionStatus.Running -> "running"
                    is ToolActionStatus.Requested -> "requested"
                }
                val msg = when (result) {
                    is ToolActionStatus.Completed -> result.message
                    is ToolActionStatus.CompletedWithData -> result.message
                    is ToolActionStatus.Failed -> result.reason
                    is ToolActionStatus.NeedsUser -> result.prompt
                    is ToolActionStatus.Running -> result.message
                    else -> ""
                }
                reportHandlerDiagnostic(ctx, call.tool, call.callId,
                    "finished:$statusName", "${elapsed}ms $msg")
                _lastStatus.value = call.callId to result
                PendingToolResultBuffer.record(toToolResult(call, result))
            } finally {
                PendingToolResultBuffer.inFlightHandlers.decrementAndGet()
            }
        }
    }

    private fun parseCall(rawJson: String): ClientToolCall? {
        return try {
            val obj = gson.fromJson(rawJson, JsonObject::class.java) ?: return null
            // Defensive type checks via the shared JsonExtensions helpers.
            val tool = obj.get("tool").asSafeString() ?: return null
            if (tool.isBlank() || !TOOL_NAME_RE.matches(tool)) {
                Log.w(TAG, "invalid tool name '$tool'")
                return null
            }
            val callId = obj.get("call_id").asSafeString() ?: return null
            if (callId.isBlank()) {
                Log.w(TAG, "empty call_id")
                return null
            }
            val argsEl: JsonElement? = obj.get("args")
            val args: JsonObject = when {
                argsEl == null || argsEl.isJsonNull -> JsonObject()
                argsEl.isJsonObject -> argsEl.asJsonObject
                else -> {
                    Log.w(TAG, "tool call 'args' is not an object: ${argsEl.javaClass.simpleName}")
                    return null
                }
            }
            ClientToolCall(tool = tool, args = args, callId = callId)
        } catch (e: Exception) {
            Log.w(TAG, "parseCall failed", e)
            null
        }
    }

    private fun toToolResult(call: ClientToolCall, status: ToolActionStatus): ToolResult {
        val (statusName, message, data) = when (status) {
            is ToolActionStatus.Requested -> Triple("running", "requested", null)
            is ToolActionStatus.Running -> Triple("running", status.message, null)
            is ToolActionStatus.Completed -> Triple("completed", status.message, null)
            is ToolActionStatus.CompletedWithData -> Triple("completed", status.message, status.data)
            is ToolActionStatus.Failed -> Triple("failed", status.reason, null)
            is ToolActionStatus.Cancelled -> Triple("cancelled", "user cancelled", null)
            is ToolActionStatus.NeedsUser -> Triple("needs_user", status.prompt, null)
        }
        return ToolResult(
            tool = call.tool,
            callId = call.callId,
            status = statusName,
            message = message,
            data = data,
        )
    }

    // ── dedupe (in-memory + persistent) ──────────────────────────────────────
    private data class SeenEntry(val callId: String, val timestamp: Long)

    private fun pruneSeen(now: Long) {
        while (true) {
            val head = seenCallIds.peekFirst() ?: return
            if (now - head.timestamp > DEDUPE_TTL_MS) {
                seenCallIds.pollFirst()
            } else return
        }
    }

    private fun isDuplicate(callId: String, now: Long, ctx: Context): Boolean {
        if (seenCallIds.any { it.callId == callId }) return true
        // Fallback: check persistent store (survives app restart)
        val prefs = ctx.getSharedPreferences(DEDUPE_PREFS, Context.MODE_PRIVATE)
        val storedTs = prefs.getLong(callId, 0L)
        return storedTs > 0 && (now - storedTs) <= DEDUPE_TTL_MS
    }

    private fun recordSeen(callId: String, now: Long, ctx: Context) {
        seenCallIds.addLast(SeenEntry(callId, now))
        val prefs = ctx.getSharedPreferences(DEDUPE_PREFS, Context.MODE_PRIVATE)
        // Use commit() (synchronous) so a crash immediately after dispatch
        // does not lose the dedupe record and re-execute the tool on restart.
        // Cost: ~1-2ms per tool call. Tool calls are rare, so this is fine.
        prefs.edit().putLong(callId, now).commit()
    }

    /**
     * Prune the persistent dedupe store exactly once per dispatcher lifetime
     * (typically once per app launch). Avoids the O(N) prefs.all walk on
     * every dispatch that the original implementation did.
     *
     * Called from inside the synchronized(dedupeLock) block, so one-shot
     * execution is race-free.
     */
    private fun pruneSharedPrefsOnce(ctx: Context, now: Long) {
        if (persistentDedupePruned) return
        persistentDedupePruned = true
        try {
            val prefs = ctx.getSharedPreferences(DEDUPE_PREFS, Context.MODE_PRIVATE)
            val editor = prefs.edit()
            var removed = 0
            prefs.all.forEach { (k, v) ->
                if (v is Long && (now - v) > DEDUPE_TTL_MS) {
                    editor.remove(k)
                    removed++
                }
            }
            if (removed > 0) {
                editor.apply()  // apply is fine for background prune
                Log.d(TAG, "pruned $removed stale dedupe entries")
            }
        } catch (e: Exception) {
            Log.w(TAG, "prune failed", e)
        }
    }

    // ── feature flag ─────────────────────────────────────────────────────────
    private fun isFeatureEnabled(ctx: Context): Boolean {
        val prefs = ctx.getSharedPreferences(com.vessences.android.util.Constants.PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getBoolean(com.vessences.android.util.Constants.PREF_PHONE_TOOLS_ENABLED, true)
    }

    /**
     * Cancel all in-flight handler coroutines and release the SupervisorJob.
     * Must be called from ChatViewModel.onCleared() to prevent leaked handlers
     * (especially countdown timers and draft-state watchers) from outliving
     * the view model.
     */
    fun shutdown() {
        try {
            job.cancel()
        } catch (e: Exception) {
            Log.w(TAG, "shutdown cancel failed", e)
        }
    }

    /**
     * Post a handler diagnostic event to the server so jane_web.log shows
     * exactly what the Android handler did, without needing device logcat.
     * Uses the same /api/device-diagnostics endpoint that AlwaysListeningService
     * already uses for wake-word diagnostics. Fire-and-forget (no retry).
     */
    private fun reportHandlerDiagnostic(ctx: Context, tool: String, callId: String, event: String, detail: String) {
        try {
            val prefs = ctx.getSharedPreferences(com.vessences.android.util.Constants.PREFS_NAME, Context.MODE_PRIVATE)
            val baseUrl = prefs.getString(com.vessences.android.util.Constants.PREF_JANE_URL, null)
                ?: com.vessences.android.util.Constants.DEFAULT_JANE_BASE_URL
            val url = "$baseUrl/api/device-diagnostics"
            val json = com.google.gson.JsonObject().apply {
                addProperty("category", "tool_handler")
                addProperty("event", "$tool:$event")
                addProperty("detail", "call_id=${callId.take(12)} $detail")
            }
            // Fire-and-forget on IO thread — don't block the handler
            scope.launch(Dispatchers.IO) {
                try {
                    val body = okhttp3.RequestBody.create(
                        "application/json".toMediaTypeOrNull(),
                        json.toString(),
                    )
                    val request = okhttp3.Request.Builder().url(url).post(body).build()
                    com.vessences.android.data.api.ApiClient.getOkHttpClient().newCall(request).execute().close()
                } catch (e: Exception) {
                    Log.d(TAG, "diagnostic post failed: ${e.message}")
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "reportHandlerDiagnostic failed: ${e.message}")
        }
    }

    companion object {
        private const val TAG = "ClientToolDispatcher"
        private const val DEDUPE_PREFS = "jane_tool_dedupe"
        private const val DEDUPE_TTL_MS = 5L * 60 * 1000  // 5 minutes
        private val TOOL_NAME_RE = Regex("""^[a-z][a-z0-9_.]*$""")
    }
}

/**
 * Thread-safe buffer of tool results waiting to be prepended to the next
 * outgoing user message.
 *
 * [ChatViewModel] drains this buffer in its send() path and formats each
 * entry as `[TOOL_RESULT:{json}]` in front of the user's text, so Jane's
 * mind sees an accurate record of what actually happened on the phone.
 */
object PendingToolResultBuffer {
    private val buf: ConcurrentLinkedDeque<ToolResult> = ConcurrentLinkedDeque()

    /**
     * Number of tool handlers currently running but not yet recorded.
     * Incremented before handler launch, decremented in finally block.
     * Used by [awaitAndDrainAll] to wait for in-flight handlers.
     */
    val inFlightHandlers = AtomicInteger(0)

    fun record(result: ToolResult) {
        buf.addLast(result)
    }

    /**
     * Wait up to [maxWaitMs] for any in-flight handlers to complete,
     * then drain all results. This prevents the race condition where
     * the user sends a message before the async handler has recorded
     * its result, causing tool results to be silently lost.
     */
    suspend fun awaitAndDrainAll(maxWaitMs: Long = 5000L): List<ToolResult> {
        if (buf.isNotEmpty() || inFlightHandlers.get() <= 0) {
            return drainAll()
        }
        // Handlers are still running — poll until they finish or timeout
        val deadline = System.currentTimeMillis() + maxWaitMs
        while (inFlightHandlers.get() > 0 && System.currentTimeMillis() < deadline) {
            kotlinx.coroutines.delay(100)
        }
        return drainAll()
    }

    /** Remove all pending results and return them in FIFO order. */
    fun drainAll(): List<ToolResult> {
        val out = mutableListOf<ToolResult>()
        while (true) {
            val item = buf.pollFirst() ?: break
            out.add(item)
        }
        return out
    }

    fun isEmpty(): Boolean = buf.isEmpty()
}
