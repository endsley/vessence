package com.vessences.android.tools

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.vessences.android.contacts.SmsSyncManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Handler for `sync.force_sms` — triggers a full re-sync of the last 14 days
 * of SMS messages to the Vessence server.
 *
 * This resets the `backfill_done` SharedPreferences flag and then calls
 * [SmsSyncManager.forceSync] which re-uploads all messages from the last
 * 14 days regardless of previous sync state.
 *
 * Triggered when the user says "sync my messages" and Jane emits:
 * `[[CLIENT_TOOL:sync.force_sms:{}]]`
 */
object SyncForceSmsHandler : ClientToolHandler {

    override val name: String = "sync.force_sms"

    private const val TAG = "SyncForceSmsHandler"

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        // Permission gate: READ_SMS is required
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return ToolActionStatus.NeedsUser("READ_SMS permission not granted")
        }

        return withContext(Dispatchers.IO) {
            try {
                Log.i(TAG, "Force SMS sync requested — resetting backfill flag and syncing")
                SmsSyncManager.forceSync(ctx)
                Log.i(TAG, "Force SMS sync completed successfully")
                ToolActionStatus.Completed("SMS sync completed — last 14 days re-synced")
            } catch (e: Exception) {
                Log.e(TAG, "Force SMS sync failed", e)
                ToolActionStatus.Failed("SMS sync failed: ${e.message}")
            }
        }
    }
}
