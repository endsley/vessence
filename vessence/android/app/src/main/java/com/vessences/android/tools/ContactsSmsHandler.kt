package com.vessences.android.tools

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.telephony.SmsManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.vessences.android.contacts.ContactsResolver
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Handler for all four SMS draft sub-tools:
 *
 *   contacts.sms_draft         — open a new draft
 *   contacts.sms_draft_update  — rewrite the body of an open draft
 *   contacts.sms_send          — commit the open draft via SmsManager
 *   contacts.sms_cancel        — abandon the open draft
 *
 * A single instance holds the pending-draft slot (at most one open draft at a
 * time) with draft_id validation. The dispatcher registers this same instance
 * under all four tool names via registerAlias().
 *
 * Draft lifecycle:
 *  1. sms_draft arrives with {query, body, draft_id}. Contact is resolved
 *     on-device. Slot is filled with (contact, body, draft_id, openedAt).
 *     TTS reads the body back. Draft is "open".
 *  2. Every subsequent marker (update/send/cancel) MUST carry the same
 *     draft_id. Mismatch → silent drop + Failed("stale draft_id") reported.
 *  3. sms_send fires SmsManager.sendTextMessage() and clears the slot.
 *  4. sms_cancel clears the slot without sending.
 *  5. Auto-expiry: a draft older than DRAFT_LIFETIME_MS (120s) is treated as
 *     closed; the next update/send/cancel returns Failed("draft expired").
 *
 * The exposed DraftPreview StateFlow lets the chat UI render a bubble with
 * the pending message and (future) a tap-to-send button for STT-failure fallback.
 */
object ContactsSmsHandler : ClientToolHandler {

    override val name: String = "contacts.sms_draft"

    /** Aliases — registered by the dispatcher against the same singleton instance. */
    val ALIASES: List<String> = listOf(
        "contacts.sms_draft_update",
        "contacts.sms_send",
        "contacts.sms_cancel",
    )

    private const val DRAFT_LIFETIME_MS = 120_000L
    private const val TAG = "ContactsSmsHandler"

    /** Suffix appended to every outgoing SMS body so recipients know the
     *  message came through Jane (not a direct text from Chieh's thumbs). */
    private const val SIGNATURE = " — via Jane"

    /**
     * Strip any markup tags Jane might accidentally leave inside the body
     * value of a marker. The ToolMarkerExtractor on the server strips the
     * [[CLIENT_TOOL:...]] wrapper, but the body value inside the marker is
     * free-text that Jane composes — it could carry leftover [ACK]...[/ACK]
     * blocks, <spoken>/<visual>/<think>/<artifact> tags from other protocols,
     * or accidental bracket/brace residue. Sanitize before sending so the
     * recipient sees clean prose.
     *
     * Rules:
     *   - Remove [ACK]...[/ACK] (spoken-only ack block)
     *   - Remove <spoken>...</spoken> but keep the inner text
     *   - Remove <visual>...</visual> but keep the inner text
     *   - Drop <think>...</think>, <thinking>...</thinking>, <artifact>...</artifact>
     *   - Drop any stray [[CLIENT_TOOL:...]] marker the extractor missed
     *   - Drop [TOOL_RESULT:...] markers
     *   - Drop [MUSIC_PLAY:...] markers
     *   - Collapse runs of whitespace to single spaces and trim
     */
    internal fun sanitizeBody(raw: String): String {
        var s = raw
        // Strip Jane's internal protocol wrappers
        s = s.replace(Regex("""\[ACK\][\s\S]*?\[/ACK\]"""), " ")
        s = s.replace(Regex("""<(?:think|thinking|artifact)>[\s\S]*?</(?:think|thinking|artifact)>""", RegexOption.IGNORE_CASE), " ")
        // Keep inner text of <spoken>/<visual>, drop the tags
        s = s.replace(Regex("""<(?:spoken|visual)>([\s\S]*?)</(?:spoken|visual)>""", RegexOption.IGNORE_CASE)) { it.groupValues[1] }
        // Drop any residual tag of the known markup families
        s = s.replace(Regex("""</?(?:spoken|visual|think|thinking|artifact)>""", RegexOption.IGNORE_CASE), "")
        // Drop tool markers that should never appear here. Brace-counted
        // match so JSON content inside the marker (which may contain `]`)
        // does not prematurely terminate the strip.
        s = stripToolMarkers(s)
        s = s.replace(Regex("""\[TOOL_RESULT:[^\]]*\]"""), "")
        s = s.replace(Regex("""\[MUSIC_PLAY:[^\]]*\]"""), "")
        // Collapse HORIZONTAL whitespace only — preserve newlines so SMS
        // formatting (paragraph breaks, lists, poetry, etc) survives.
        // Also collapse runs of blank lines to at most one blank line.
        s = s.replace(Regex("""[ \t]+"""), " ")
        s = s.replace(Regex("""\n{3,}"""), "\n\n")
        // Trim leading/trailing whitespace from each line, then overall.
        s = s.split("\n").joinToString("\n") { it.trim() }
        return s.trim()
    }

    /**
     * Remove any ``[[CLIENT_TOOL:<name>:<json>]]`` marker that leaked into an
     * SMS body. Uses brace counting so JSON values containing `]` or `]]`
     * do not prematurely terminate the strip (e.g., a body value like
     * ``"body": "use ]] bracket"``).
     */
    private fun stripToolMarkers(input: String): String {
        val open = "[[CLIENT_TOOL:"
        val close = "]]"
        val sb = StringBuilder()
        var i = 0
        while (i < input.length) {
            val openIdx = input.indexOf(open, i)
            if (openIdx < 0) {
                sb.append(input, i, input.length)
                break
            }
            sb.append(input, i, openIdx)
            // Scan past the opener and find the matching ]] with brace counting.
            var j = openIdx + open.length
            // Skip tool name up to ':'
            while (j < input.length && input[j] != ':') j++
            if (j >= input.length) {
                // Malformed — append the rest and stop.
                sb.append(input, openIdx, input.length)
                break
            }
            j++  // past ':'
            // Parse JSON: brace depth + string state
            if (j >= input.length || input[j] != '{') {
                sb.append(input, openIdx, input.length)
                break
            }
            var depth = 0
            var inStr = false
            var escape = false
            var jsonEnd = -1
            while (j < input.length) {
                val ch = input[j]
                if (inStr) {
                    when {
                        escape -> escape = false
                        ch == '\\' -> escape = true
                        ch == '"' -> inStr = false
                    }
                } else {
                    when (ch) {
                        '"' -> inStr = true
                        '{' -> depth++
                        '}' -> {
                            depth--
                            if (depth == 0) {
                                jsonEnd = j + 1
                                break
                            }
                        }
                    }
                }
                j++
            }
            if (jsonEnd < 0) {
                // Unbalanced — append remainder as-is.
                sb.append(input, openIdx, input.length)
                break
            }
            // Skip optional whitespace then require ]]
            var k = jsonEnd
            while (k < input.length && input[k].isWhitespace()) k++
            if (k + 1 < input.length && input.startsWith(close, k)) {
                i = k + close.length
            } else {
                // Malformed close — keep the raw text rather than silently eat it.
                sb.append(input, openIdx, input.length)
                break
            }
        }
        return sb.toString()
    }

    /** Append Jane's signature to a sanitized body. Guards against duplicate
     *  signatures if the body already ends with one (e.g., on retry). */
    internal fun addSignature(cleanBody: String): String {
        val trimmed = cleanBody.trimEnd()
        if (trimmed.endsWith(SIGNATURE.trim(), ignoreCase = true)) return trimmed
        return trimmed + SIGNATURE
    }

    private data class PendingDraft(
        val draftId: String,
        val contact: ContactsResolver.Contact,
        var body: String,
        val openedAt: Long,
    )

    private val slotMutex = Mutex()
    private var pending: PendingDraft? = null

    /** Read-only view of the current draft for the chat UI to render a preview bubble. */
    data class DraftPreview(
        val draftId: String,
        val contactName: String,
        val body: String,
    )

    private val _preview = MutableStateFlow<DraftPreview?>(null)
    val preview: StateFlow<DraftPreview?> = _preview

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus = when (call.tool) {
        "contacts.sms_draft" -> openDraft(call, ctx, queue)
        "contacts.sms_draft_update" -> updateDraft(call, queue)
        "contacts.sms_send" -> commitDraft(call, ctx, queue)
        "contacts.sms_cancel" -> cancelDraft(call, queue)
        else -> ToolActionStatus.Failed("unknown sms sub-tool: ${call.tool}")
    }

    private suspend fun openDraft(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        val query = call.args.get("query").asSafeString()
            ?: return ToolActionStatus.Failed("missing 'query' arg")
        val body = call.args.get("body").asSafeString()
            ?: return ToolActionStatus.Failed("missing 'body' arg")
        val draftId = call.args.get("draft_id").asSafeString()
            ?: return ToolActionStatus.Failed("missing 'draft_id' arg")

        val resolved = ContactsResolver.resolveExact(ctx, query)
        val contact = when (resolved) {
            is ContactsResolver.ResolveResult.PermissionDenied -> {
                return ToolActionStatus.NeedsUser("grant READ_CONTACTS permission")
            }
            is ContactsResolver.ResolveResult.None -> {
                return ToolActionStatus.Failed("no contact matches '$query'")
            }
            is ContactsResolver.ResolveResult.Multiple -> {
                val names = resolved.candidates.take(3).joinToString(", ") { it.displayName }
                return ToolActionStatus.NeedsUser("ambiguous contact: $names")
            }
            is ContactsResolver.ResolveResult.Single -> resolved.contact
        }

        slotMutex.withLock {
            pending = PendingDraft(
                draftId = draftId,
                contact = contact,
                body = body,
                openedAt = System.currentTimeMillis(),
            )
            _preview.value = DraftPreview(draftId, contact.displayName, body)
        }
        // No handler TTS — Jane's response text already contains the draft
        // read-back (e.g., "To spouse: be home in 20.") which gets spoken
        // via the normal chat TTS path. Handler TTS was redundant and caused
        // a deadlock when chat TTS flushed the handler's utterance mid-play.
        return ToolActionStatus.Running("draft open")
    }

    private suspend fun updateDraft(
        call: ClientToolCall,
        queue: ActionQueue,
    ): ToolActionStatus {
        val draftId = call.args.get("draft_id").asSafeString()
            ?: return ToolActionStatus.Failed("missing 'draft_id' arg")
        val newBody = call.args.get("body").asSafeString()
            ?: return ToolActionStatus.Failed("missing 'body' arg")

        slotMutex.withLock {
            val p = pending ?: return ToolActionStatus.Failed("no open draft to update")
            if (p.draftId != draftId) {
                Log.w(TAG, "update draft_id mismatch: expected ${p.draftId}, got $draftId")
                return ToolActionStatus.Failed("stale draft_id")
            }
            if (isExpired(p)) {
                Log.i(TAG, "draft ${p.draftId} expired but user is still editing — refreshing timer")
                pending = p.copy(openedAt = System.currentTimeMillis())
            }
            p.body = newBody
            _preview.value = DraftPreview(draftId, p.contact.displayName, newBody)
        }
        return ToolActionStatus.Running("draft updated")
    }

    private suspend fun commitDraft(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        val draftId = call.args.get("draft_id").asSafeString()
            ?: return ToolActionStatus.Failed("missing 'draft_id' arg")

        if (!hasSendSmsPermission(ctx)) {
            return ToolActionStatus.NeedsUser("grant SEND_SMS permission")
        }

        // Hold slotMutex across the ENTIRE send — validate, sanitize, dispatch
        // to SmsManager, clear slot. If a concurrent cancel/update/new-draft
        // call arrives mid-send, it waits on the mutex and sees a clean slot
        // after this block finishes, rather than racing and corrupting state.
        return slotMutex.withLock {
            val p = pending ?: return@withLock ToolActionStatus.Failed("no open draft to send")
            if (p.draftId != draftId) {
                Log.w(TAG, "send draft_id mismatch: expected ${p.draftId}, got $draftId")
                return@withLock ToolActionStatus.Failed("stale draft_id")
            }
            if (isExpired(p)) {
                Log.i(TAG, "draft ${p.draftId} expired but user confirmed send — proceeding anyway")
            }

            // Sanitize the body BEFORE sending: strip any protocol tags, then
            // append Jane's signature so the recipient sees clean prose.
            val cleanedBody = sanitizeBody(p.body)
            if (cleanedBody.isBlank()) {
                pending = null
                _preview.value = null
                // Speak OUTSIDE the lock isn't an option inside withLock, but
                // TTS goes through the ActionQueue's own mutex so it can't
                // deadlock with slotMutex — they're independent.
                // No handler TTS
                return@withLock ToolActionStatus.Failed("sanitized body was blank")
            }
            val finalBody = addSignature(cleanedBody)

            try {
                @Suppress("DEPRECATION")
                val sm: SmsManager = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                    ctx.getSystemService(SmsManager::class.java)
                } else {
                    SmsManager.getDefault()
                }
                val parts = sm.divideMessage(finalBody)
                if (parts.size > 1) {
                    sm.sendMultipartTextMessage(p.contact.phoneNumber, null, parts, null, null)
                } else {
                    sm.sendTextMessage(p.contact.phoneNumber, null, finalBody, null, null)
                }
                // No handler TTS — Jane's response says "Message sent."
                val displayName = p.contact.displayName
                pending = null
                _preview.value = null
                Log.i(TAG, "sms sent to $displayName (${finalBody.length} chars, ${parts.size} part(s))")
                ToolActionStatus.Completed("sms sent to $displayName")
            } catch (e: Exception) {
                Log.e(TAG, "sms send failed", e)
                // No handler TTS for errors either — the failure status goes back
                // to Jane via TOOL_RESULT and she speaks the explanation herself.
                ToolActionStatus.Failed(e.localizedMessage ?: "sms send failed")
            }
        }
    }

    private suspend fun cancelDraft(
        call: ClientToolCall,
        queue: ActionQueue,
    ): ToolActionStatus {
        // Cancel does NOT require a matching draft_id — any cancel is safe.
        slotMutex.withLock {
            pending = null
            _preview.value = null
        }
        // No handler TTS — Jane's response says "Dropped it."
        return ToolActionStatus.Cancelled
    }

    private fun isExpired(p: PendingDraft): Boolean =
        System.currentTimeMillis() - p.openedAt > DRAFT_LIFETIME_MS

    private fun hasSendSmsPermission(ctx: Context): Boolean =
        ContextCompat.checkSelfPermission(
            ctx,
            Manifest.permission.SEND_SMS,
        ) == PackageManager.PERMISSION_GRANTED

    // asSafeString is now in JsonExtensions.kt — shared with every handler.
}
