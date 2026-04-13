package com.vessences.android.tools

import android.content.Context
import android.util.Log
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

/**
 * Handler for `device.speak_time` — speaks the phone's current local time
 * (and day of week) via the shared [ActionQueue] TTS path.
 *
 * The phone is authoritative for the user's timezone, so Stage 2 of the
 * intent classifier delegates GET_TIME to the client instead of computing
 * server-side (server may be in a different TZ).
 *
 * Args: none expected. Any payload is ignored.
 */
object DeviceSpeakTimeHandler : ClientToolHandler {

    override val name: String = "device.speak_time"

    private const val TAG = "DeviceSpeakTime"

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus {
        val now = Calendar.getInstance()
        // e.g. "3:47 PM" — uses device locale for AM/PM vs 24h conventions.
        val timeFmt = SimpleDateFormat("h:mm a", Locale.getDefault())
        val dayFmt = SimpleDateFormat("EEEE, MMMM d", Locale.getDefault())
        val timeStr = timeFmt.format(now.time)
        val dayStr = dayFmt.format(now.time)
        val spoken = "It's $timeStr on $dayStr."
        queue.speak(spoken)
        Log.i(TAG, "spoke time: $spoken")
        return ToolActionStatus.Completed(spoken)
    }
}
