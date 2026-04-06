package com.vessences.android.tools

import android.content.Context

/**
 * Contract for a client-side tool handler.
 *
 * A handler claims one tool [name] (e.g., "contacts.call") and is invoked by
 * [ClientToolDispatcher] when a matching [ClientToolCall] arrives from the server.
 *
 * Implementations MUST:
 *  - Perform disk / content resolver work on `Dispatchers.IO`.
 *  - Perform UI work (dialogs, activity launches) on `Dispatchers.Main`.
 *  - Route all TTS and external-intent launches through the provided [ActionQueue]
 *    so tool audio serializes correctly with the chat stream and other handlers.
 *  - Return a terminal [ToolActionStatus] so the dispatcher can emit a TOOL_RESULT
 *    feedback entry for Jane's next turn.
 *
 * Handlers are registered at dispatcher init time and share a single [ActionQueue]
 * for the life of the process.
 */
interface ClientToolHandler {
    /** Tool name as it appears in `[[CLIENT_TOOL:<name>:<json>]]`. */
    val name: String

    /**
     * Execute the tool. Caller awaits. Implementation must not throw — any error
     * path should produce a [ToolActionStatus.Failed] instead.
     *
     * @param call the parsed tool call from the server
     * @param ctx application context (prefer this over activity contexts since
     *   handlers may outlive any single activity)
     * @param queue the shared action queue for serializing TTS and intent launches
     */
    suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus
}
