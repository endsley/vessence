package com.vessences.android.tools

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import org.json.JSONArray
import org.json.JSONObject

/**
 * Handler for three client-side timer tools:
 *   timer.set    — schedule a one-shot AlarmManager.setAlarmClock()
 *   timer.cancel — cancel all outstanding timers
 *   timer.list   — enumerate outstanding timers (fires back via CompletedWithData)
 *
 * Why AlarmManager.setAlarmClock(): it is exact, survives Doze, and fires
 * even when the device is offline or the app is killed. The timer rings on
 * the phone itself — no server roundtrip needed.
 *
 * Timer book (persisted): a JSON array in SharedPreferences so list/cancel
 * can enumerate outstanding alarms across process restarts. Each entry is
 * {id:int, fireAt:long(ms), label:string}.
 */
object TimerHandler : ClientToolHandler {

    override val name: String = "timer.set"
    val ALIASES: List<String> = listOf("timer.cancel", "timer.list", "timer.delete")

    private const val TAG = "TimerHandler"
    private const val PREFS = "jane_timers"
    private const val KEY_BOOK = "book"
    private const val KEY_NEXT_ID = "next_id"
    const val CHANNEL_ID = "jane_timer_ringing"
    const val ACTION_FIRE = "com.vessences.android.TIMER_FIRE"
    const val EXTRA_TIMER_ID = "timer_id"
    const val EXTRA_LABEL = "timer_label"

    override suspend fun handle(
        call: ClientToolCall,
        ctx: Context,
        queue: ActionQueue,
    ): ToolActionStatus = when (call.tool) {
        "timer.set" -> setTimer(call, ctx)
        "timer.cancel" -> cancelAll(ctx)
        "timer.list" -> listTimers(ctx)
        "timer.delete" -> deleteTimer(call, ctx)
        else -> ToolActionStatus.Failed("unknown timer sub-tool: ${call.tool}")
    }

    // ── set ──────────────────────────────────────────────────────────────────
    private fun setTimer(call: ClientToolCall, ctx: Context): ToolActionStatus {
        val durationMs = call.args.get("duration_ms")?.let {
            if (it.isJsonPrimitive) it.asJsonPrimitive.asLong else 0L
        } ?: 0L
        if (durationMs <= 0) return ToolActionStatus.Failed("invalid duration_ms")
        val label = call.args.get("label").asSafeString().orEmpty()

        ensureChannel(ctx)
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as AlarmManager

        // On Android 12+ exact alarms require SCHEDULE_EXACT_ALARM or the
        // user-granted USE_EXACT_ALARM. setAlarmClock() is the one API that
        // works regardless — reserved for user-visible alarm clock use cases,
        // which is exactly what this is. No permission needed.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !am.canScheduleExactAlarms()) {
            Log.i(TAG, "exact alarms not granted; relying on setAlarmClock privilege")
        }

        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val id = prefs.getInt(KEY_NEXT_ID, 1)
        val fireAt = System.currentTimeMillis() + durationMs

        val fireIntent = Intent(ctx, TimerFireReceiver::class.java).apply {
            action = ACTION_FIRE
            putExtra(EXTRA_TIMER_ID, id)
            putExtra(EXTRA_LABEL, label)
        }
        val pi = PendingIntent.getBroadcast(
            ctx, id, fireIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        // Show-intent: tapping the alarm-clock icon in the status bar opens
        // the app. Use MainActivity.
        val showIntent = PendingIntent.getActivity(
            ctx, id,
            Intent(ctx, Class.forName("com.vessences.android.MainActivity")),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val info = AlarmManager.AlarmClockInfo(fireAt, showIntent)
        am.setAlarmClock(info, pi)

        // Persist the timer entry
        appendToBook(prefs, id, fireAt, label)
        prefs.edit().putInt(KEY_NEXT_ID, id + 1).apply()

        Log.i(TAG, "timer #$id set for ${durationMs}ms (label='$label')")
        return ToolActionStatus.Completed("timer set for ${durationMs}ms")
    }

    // ── cancel ───────────────────────────────────────────────────────────────
    private fun cancelAll(ctx: Context): ToolActionStatus {
        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val book = readBook(prefs)
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        var count = 0
        for (i in 0 until book.length()) {
            val entry = book.optJSONObject(i) ?: continue
            val id = entry.optInt("id", -1)
            if (id < 0) continue
            val intent = Intent(ctx, TimerFireReceiver::class.java).apply {
                action = ACTION_FIRE
            }
            val pi = PendingIntent.getBroadcast(
                ctx, id, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            am.cancel(pi)
            count++
        }
        prefs.edit().putString(KEY_BOOK, "[]").apply()
        Log.i(TAG, "cancelled $count timer(s)")
        return ToolActionStatus.Completed("cancelled $count timer(s)")
    }

    // ── delete specific ──────────────────────────────────────────────────────
    //
    // Args (any one of):
    //   "id"    : int — specific timer id from a previous list
    //   "label" : str — delete the first timer whose label matches (case-insensitive)
    //   "index" : int — 1-based index into the chronologically-ordered list
    private fun deleteTimer(call: ClientToolCall, ctx: Context): ToolActionStatus {
        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val book = pruneExpired(prefs, readBook(prefs))
        val idArg = call.args.get("id")?.let {
            if (it.isJsonPrimitive) it.asJsonPrimitive.asInt else -1
        } ?: -1
        val labelArg = call.args.get("label").asSafeString().orEmpty().lowercase()
        val indexArg = call.args.get("index")?.let {
            if (it.isJsonPrimitive) it.asJsonPrimitive.asInt else -1
        } ?: -1

        var targetIdx = -1
        var targetId = -1
        var targetLabel = ""
        for (i in 0 until book.length()) {
            val e = book.optJSONObject(i) ?: continue
            val eid = e.optInt("id", -1)
            val elabel = e.optString("label", "")
            val match = when {
                idArg > 0 -> eid == idArg
                indexArg > 0 -> (i + 1) == indexArg
                labelArg.isNotBlank() -> elabel.lowercase().contains(labelArg)
                else -> false
            }
            if (match) {
                targetIdx = i
                targetId = eid
                targetLabel = elabel
                break
            }
        }
        if (targetIdx < 0) {
            return ToolActionStatus.Failed(
                "no matching timer (id=$idArg label='$labelArg' index=$indexArg)"
            )
        }

        // Cancel the AlarmManager-registered alarm
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val intent = Intent(ctx, TimerFireReceiver::class.java).apply { action = ACTION_FIRE }
        val pi = PendingIntent.getBroadcast(
            ctx, targetId, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        am.cancel(pi)

        // Remove from the book
        val out = JSONArray()
        for (i in 0 until book.length()) {
            if (i == targetIdx) continue
            book.optJSONObject(i)?.let { out.put(it) }
        }
        prefs.edit().putString(KEY_BOOK, out.toString()).apply()
        val label = if (targetLabel.isBlank()) "timer #$targetId" else "$targetLabel timer"
        Log.i(TAG, "deleted $label (id=$targetId)")
        return ToolActionStatus.Completed("deleted $label")
    }

    // ── list ─────────────────────────────────────────────────────────────────
    private fun listTimers(ctx: Context): ToolActionStatus {
        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val book = pruneExpired(prefs, readBook(prefs))
        val now = System.currentTimeMillis()
        val summary = StringBuilder()
        for (i in 0 until book.length()) {
            val e = book.optJSONObject(i) ?: continue
            val remaining = e.optLong("fireAt") - now
            if (remaining <= 0) continue
            val mins = remaining / 60_000
            val secs = (remaining / 1000) % 60
            val label = e.optString("label").takeIf { it.isNotBlank() }
            summary.append("• ")
            if (label != null) summary.append("$label: ")
            summary.append("${mins}m ${secs}s remaining\n")
        }
        val text = if (summary.isEmpty()) "No timers running." else summary.toString().trim()
        val payload = com.google.gson.JsonObject().apply {
            addProperty("timers", book.toString())
        }
        return ToolActionStatus.CompletedWithData(text, payload)
    }

    // ── book helpers ─────────────────────────────────────────────────────────
    private fun readBook(prefs: SharedPreferences): JSONArray =
        try { JSONArray(prefs.getString(KEY_BOOK, "[]") ?: "[]") } catch (_: Exception) { JSONArray() }

    private fun appendToBook(prefs: SharedPreferences, id: Int, fireAt: Long, label: String) {
        val book = pruneExpired(prefs, readBook(prefs))
        book.put(JSONObject().apply {
            put("id", id); put("fireAt", fireAt); put("label", label)
        })
        prefs.edit().putString(KEY_BOOK, book.toString()).apply()
    }

    private fun pruneExpired(prefs: SharedPreferences, book: JSONArray): JSONArray {
        val now = System.currentTimeMillis()
        val out = JSONArray()
        for (i in 0 until book.length()) {
            val e = book.optJSONObject(i) ?: continue
            if (e.optLong("fireAt") > now) out.put(e)
        }
        if (out.length() != book.length()) {
            prefs.edit().putString(KEY_BOOK, out.toString()).apply()
        }
        return out
    }

    internal fun removeFromBook(ctx: Context, id: Int) {
        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val book = readBook(prefs)
        val out = JSONArray()
        for (i in 0 until book.length()) {
            val e = book.optJSONObject(i) ?: continue
            if (e.optInt("id", -1) != id) out.put(e)
        }
        prefs.edit().putString(KEY_BOOK, out.toString()).apply()
    }

    internal fun ensureChannel(ctx: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID, "Timer Ringing", NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Fires when a Jane timer goes off"
            setSound(null, null)
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 500, 250, 500)
        }
        nm.createNotificationChannel(channel)
    }
}

/**
 * BroadcastReceiver that fires when a timer alarm goes off. Speaks the
 * label via TTS (e.g. "Hey, the bread is ready") and posts a silent
 * notification as a visual backup. No alarm sound is played.
 */
class TimerFireReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val ctx = context.applicationContext
        val id = intent.getIntExtra(TimerHandler.EXTRA_TIMER_ID, 0)
        val label = intent.getStringExtra(TimerHandler.EXTRA_LABEL).orEmpty()
        TimerHandler.ensureChannel(ctx)
        TimerHandler.removeFromBook(ctx, id)

        val spoken = if (label.isNotBlank()) "Hey, the $label is ready." else "Hey, your timer is up."

        // Speak via TTS instead of ringtone
        val pending = goAsync()
        var ttsEngine: android.speech.tts.TextToSpeech? = null
        ttsEngine = android.speech.tts.TextToSpeech(ctx) { status ->
            if (status == android.speech.tts.TextToSpeech.SUCCESS) {
                val params = android.os.Bundle().apply {
                    putInt(android.speech.tts.TextToSpeech.Engine.KEY_PARAM_STREAM,
                        android.media.AudioManager.STREAM_ALARM)
                }
                ttsEngine?.setOnUtteranceProgressListener(object : android.speech.tts.UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {}
                    override fun onDone(utteranceId: String?) {
                        ttsEngine?.shutdown()
                        pending.finish()
                    }
                    override fun onError(utteranceId: String?) {
                        ttsEngine?.shutdown()
                        pending.finish()
                    }
                })
                ttsEngine?.speak(spoken, android.speech.tts.TextToSpeech.QUEUE_FLUSH, params, "timer_$id")
                Log.i("TimerFireReceiver", "TTS speaking: $spoken")
            } else {
                // TTS init failed — post notification silently (no alarm sound)
                Log.w("TimerFireReceiver", "TTS init failed; notification only")
                pending.finish()
            }
        }

        val title = if (label.isNotBlank()) "Timer: $label" else "Timer"
        val notifText = if (label.isNotBlank()) "The $label is ready." else "Time's up."
        val openIntent = Intent(ctx, Class.forName("com.vessences.android.MainActivity"))
        val openPi = PendingIntent.getActivity(
            ctx, id + 100_000, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notif = NotificationCompat.Builder(ctx, TimerHandler.CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(title)
            .setContentText(notifText)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setAutoCancel(true)
            .setFullScreenIntent(openPi, true)
            .setContentIntent(openPi)
            .build()
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(200_000 + id, notif)
        Log.i("TimerFireReceiver", "timer #$id fired (label='$label')")
    }
}
