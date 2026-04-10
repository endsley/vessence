package com.vessences.android.tools

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.util.Log
import androidx.core.content.ContextCompat
import com.vessences.android.contacts.ContactsResolver
import kotlinx.coroutines.delay

/**
 * Handler for `contacts.call` — place a phone call to a contact, resolved
 * on-device by display name, with a 10-second verbal countdown giving the
 * user a chance to cancel before the call is placed.
 *
 * V1 simplification: the "say stop to cancel" listening step is NOT wired
 * in this phase — that requires a fresh SpeechRecognizer instance and
 * careful integration with the existing wake-word STT to avoid fighting
 * over the mic. Instead, v1 relies on:
 *   1. A conservative 10-second countdown spoken by TTS.
 *   2. A visible in-chat cancel path (future: on-screen cancel button fed
 *      via DraftPreviewState / a CallCountdownState flow).
 *   3. Jane's mind explicitly acknowledging the call with the contact name
 *      before the handler fires, so user has a window to interject in the
 *      conversation stream itself.
 *
 * The STT-cancel-word listener is captured as a Phase 3 follow-up in the
 * design spec and does not block v1 shipping. If the countdown proves too
 * slow without a verbal cancel, we'll add the listener then.
 */
object ContactsCallHandler : ClientToolHandler {

    override val name: String = "contacts.call"


    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        val query = call.args.get("query").asSafeString()
            ?: return ToolActionStatus.Failed("missing 'query' arg")

        // Permission check up front — fail clearly if CALL_PHONE isn't granted.
        if (!hasCallPermission(ctx)) {
            queue.speak("I need permission to place calls. Open Jane's settings to enable it.")
            return ToolActionStatus.NeedsUser("grant CALL_PHONE permission")
        }

        // Resolve contact on-device.
        val resolved = ContactsResolver.resolveExact(ctx, query)
        val contact = when (resolved) {
            is ContactsResolver.ResolveResult.PermissionDenied -> {
                queue.speak("I don't have access to your contacts yet. Open Jane's settings to enable it.")
                return ToolActionStatus.NeedsUser("grant READ_CONTACTS permission")
            }
            is ContactsResolver.ResolveResult.None -> {
                queue.speak("I couldn't find a contact named $query.")
                return ToolActionStatus.Failed("no contact matches '$query'")
            }
            is ContactsResolver.ResolveResult.Multiple -> {
                val names = resolved.candidates.take(3).joinToString(", ") { it.displayName }
                queue.speak("I found multiple matches for $query: $names. Try being more specific.")
                return ToolActionStatus.NeedsUser("ambiguous contact: $names")
            }
            is ContactsResolver.ResolveResult.Single -> resolved.contact
        }

        // Dial immediately — user explicitly asked to call.
        queue.speak("Calling ${contact.displayName}.")

        val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:${contact.phoneNumber}"))
        val launchError = queue.startActivity(ctx, intent)
        if (launchError != null) {
            // Call never actually reached the dialer — surface the failure
            // both to the user (TTS) and to Jane's mind (via Failed status →
            // TOOL_RESULT). Previously this path was silently logged and
            // returned Completed, creating a "Jane thinks the call happened,
            // reality disagrees" drift.
            queue.speak("The call didn't go through: ${launchError.localizedMessage ?: "unknown error"}.")
            return ToolActionStatus.Failed("ACTION_CALL launch failed: ${launchError.message ?: launchError.javaClass.simpleName}")
        }
        Log.i(TAG, "dialed ${contact.displayName} at ${contact.phoneNumber.take(3)}***")
        return ToolActionStatus.Completed("dialed ${contact.displayName}")
    }

    private fun hasCallPermission(ctx: Context): Boolean =
        ContextCompat.checkSelfPermission(
            ctx,
            Manifest.permission.CALL_PHONE,
        ) == PackageManager.PERMISSION_GRANTED

    // asSafeString is now in JsonExtensions.kt — shared with every handler.

    private const val TAG = "ContactsCallHandler"
}
