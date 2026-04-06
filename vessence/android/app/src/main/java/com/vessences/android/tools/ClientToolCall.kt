package com.vessences.android.tools

import com.google.gson.JsonObject

/**
 * A tool invocation request sent from Jane's mind (server) to the Android client
 * via the `client_tool_call` SSE event.
 *
 * The server's ToolMarkerExtractor parses [[CLIENT_TOOL:<name>:<json_args>]] markers
 * out of Jane's streaming output and emits them as structured events in this shape.
 *
 * - [tool] is the tool name (e.g., "contacts.call", "contacts.sms_draft").
 * - [args] is the raw arguments JSON object.
 * - [callId] is a server-generated UUID used for replay/reconnect dedupe.
 */
data class ClientToolCall(
    val tool: String,
    val args: JsonObject,
    val callId: String,
)

/**
 * Terminal (and some intermediate) states a tool handler can produce.
 *
 * These flow into PendingToolResultBuffer and are prepended as [TOOL_RESULT:{json}]
 * markers on the user's next outgoing message so Jane's mind stays in sync with
 * what actually happened on the phone.
 */
sealed class ToolActionStatus {
    /** Handler received the call and passed validation. */
    object Requested : ToolActionStatus()

    /** Handler is mid-flight (e.g., 10s countdown running, draft open). */
    data class Running(val message: String) : ToolActionStatus()

    /** Handler completed successfully. */
    data class Completed(val message: String) : ToolActionStatus()

    /**
     * Handler completed successfully AND wants to ship a structured data
     * payload back to Jane's mind via the TOOL_RESULT feedback channel.
     * Used by fetch-style tools (e.g., messages.fetch_unread) that return
     * a list of records for Jane to reason about.
     */
    data class CompletedWithData(val message: String, val data: JsonObject) : ToolActionStatus()

    /** Handler failed (permission denied, no match, send failed, etc). */
    data class Failed(val reason: String) : ToolActionStatus()

    /** Handler ran to termination because the user cancelled mid-flight. */
    object Cancelled : ToolActionStatus()

    /**
     * Handler needs additional user input before it can proceed.
     * The [prompt] is a short human-readable hint (e.g., "ambiguous contact",
     * "grant CALL_PHONE permission"). Jane's mind will see this via the
     * TOOL_RESULT feedback channel and can ask a clarifying question on the
     * next turn.
     */
    data class NeedsUser(val prompt: String) : ToolActionStatus()
}

/**
 * A tool result destined for the server-side Jane, piggybacked on the next
 * outgoing user message as `[TOOL_RESULT:{json}]...`.
 *
 * The optional [data] field carries arbitrary structured payload — used by
 * tools like `messages.fetch_unread` that need to return a list of records
 * for Jane's mind to reason about. Must be a Gson [JsonObject]; serializes
 * inline into the marker payload.
 */
data class ToolResult(
    val tool: String,
    val callId: String,
    val status: String,      // "completed" | "failed" | "cancelled" | "needs_user" | "unsupported"
    val message: String,
    val extra: Map<String, String> = emptyMap(),
    val data: JsonObject? = null,
)
