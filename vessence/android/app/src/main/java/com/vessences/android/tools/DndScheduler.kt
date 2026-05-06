package com.vessences.android.tools

import android.app.AlarmManager
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.vessences.android.util.Constants
import java.util.Calendar

/**
 * Quiet Hours: flips the OS into Priority-only DND at the user's start time and
 * back to All at the end time, daily. Vessences notification channels in
 * BYPASS_DND_CHANNELS are flagged setBypassDnd(true) so Jane's alerts still
 * come through while calls / SMS / other apps stay silent.
 *
 * State ownership: we only mutate the OS interruption filter when we are
 * currently the "owner" of it — i.e. we previously turned DND on. This
 * prevents Quiet Hours from clobbering the user's manual DND, a Bedtime rule,
 * or another app's DND policy. Ownership is tracked in PREF_DND_OWNS_STATE.
 *
 * Scheduling pattern: one-shot setExactAndAllowWhileIdle alarms that re-arm
 * themselves from the receiver. This survives Doze and reboots (paired with
 * BOOT_COMPLETED) without needing a long-running service.
 */
object DndScheduler {

    private const val TAG = "DndScheduler"
    const val ACTION_DND_ON = "com.vessences.android.DND_ON"
    const val ACTION_DND_OFF = "com.vessences.android.DND_OFF"
    private const val REQ_ON = 71_001
    private const val REQ_OFF = 71_002
    private const val PREF_DND_OWNS_STATE = "dnd_owns_state"

    /**
     * Channels permitted to bypass DND during Quiet Hours. Adding to this list
     * is an intentional decision — most channels (background service status,
     * share-receiver progress, etc.) should stay silenced.
     */
    private val BYPASS_DND_CHANNELS = setOf(
        "chat_jane_messages",
        "chat_amber_messages",
        TimerHandler.CHANNEL_ID,
    )

    fun isEnabled(ctx: Context): Boolean =
        prefs(ctx).getBoolean(Constants.PREF_DND_ENABLED, false)

    fun setEnabled(ctx: Context, enabled: Boolean) {
        prefs(ctx).edit().putBoolean(Constants.PREF_DND_ENABLED, enabled).apply()
        if (enabled) applyAndSchedule(ctx) else cancelAll(ctx)
    }

    fun getStart(ctx: Context): Pair<Int, Int> {
        val p = prefs(ctx)
        return p.getInt(Constants.PREF_DND_START_HOUR, Constants.DEFAULT_DND_START_HOUR) to
            p.getInt(Constants.PREF_DND_START_MINUTE, Constants.DEFAULT_DND_START_MINUTE)
    }

    fun getEnd(ctx: Context): Pair<Int, Int> {
        val p = prefs(ctx)
        return p.getInt(Constants.PREF_DND_END_HOUR, Constants.DEFAULT_DND_END_HOUR) to
            p.getInt(Constants.PREF_DND_END_MINUTE, Constants.DEFAULT_DND_END_MINUTE)
    }

    fun setStart(ctx: Context, hour: Int, minute: Int) {
        prefs(ctx).edit()
            .putInt(Constants.PREF_DND_START_HOUR, hour)
            .putInt(Constants.PREF_DND_START_MINUTE, minute)
            .apply()
        if (isEnabled(ctx)) applyAndSchedule(ctx)
    }

    fun setEnd(ctx: Context, hour: Int, minute: Int) {
        prefs(ctx).edit()
            .putInt(Constants.PREF_DND_END_HOUR, hour)
            .putInt(Constants.PREF_DND_END_MINUTE, minute)
            .apply()
        if (isEnabled(ctx)) applyAndSchedule(ctx)
    }

    /**
     * Apply the correct DND state for the current wall-clock time and arm both
     * the next ON and next OFF alarms. Safe to call repeatedly.
     */
    fun applyAndSchedule(ctx: Context) {
        ensureBypassDnd(ctx)
        if (!hasPolicyAccess(ctx)) {
            Log.w(TAG, "policy access not granted; skipping apply")
            scheduleNext(ctx)
            return
        }
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val current = nm.currentInterruptionFilter
        val owns = prefs(ctx).getBoolean(PREF_DND_OWNS_STATE, false)
        val inWindow = isInQuietWindow(ctx)

        if (inWindow) {
            // Only escalate if no stricter (or equal) filter is already active.
            // PRIORITY (2) < ALARMS (3) < NONE (4) — leave stricter alone.
            if (current == NotificationManager.INTERRUPTION_FILTER_ALL ||
                current == NotificationManager.INTERRUPTION_FILTER_UNKNOWN
            ) {
                trySetFilter(nm, NotificationManager.INTERRUPTION_FILTER_PRIORITY)
                prefs(ctx).edit().putBoolean(PREF_DND_OWNS_STATE, true).apply()
            }
        } else {
            // Only relax if we are the ones who set DND. Don't override the
            // user's manual DND or another app's policy.
            if (owns && current == NotificationManager.INTERRUPTION_FILTER_PRIORITY) {
                trySetFilter(nm, NotificationManager.INTERRUPTION_FILTER_ALL)
            }
            prefs(ctx).edit().putBoolean(PREF_DND_OWNS_STATE, false).apply()
        }
        scheduleNext(ctx)
    }

    fun cancelAll(ctx: Context) {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        am.cancel(pendingIntent(ctx, ACTION_DND_ON, REQ_ON))
        am.cancel(pendingIntent(ctx, ACTION_DND_OFF, REQ_OFF))
        // Only lift DND we set ourselves.
        if (hasPolicyAccess(ctx) && prefs(ctx).getBoolean(PREF_DND_OWNS_STATE, false)) {
            val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (nm.currentInterruptionFilter == NotificationManager.INTERRUPTION_FILTER_PRIORITY) {
                trySetFilter(nm, NotificationManager.INTERRUPTION_FILTER_ALL)
            }
        }
        prefs(ctx).edit().putBoolean(PREF_DND_OWNS_STATE, false).apply()
        Log.i(TAG, "quiet hours disabled, alarms cancelled")
    }

    fun isInQuietWindow(ctx: Context): Boolean {
        val (sh, sm) = getStart(ctx)
        val (eh, em) = getEnd(ctx)
        val now = Calendar.getInstance()
        val curMin = now.get(Calendar.HOUR_OF_DAY) * 60 + now.get(Calendar.MINUTE)
        val startMin = sh * 60 + sm
        val endMin = eh * 60 + em
        return if (startMin == endMin) {
            false
        } else if (startMin < endMin) {
            curMin in startMin until endMin
        } else {
            // Window wraps midnight (typical: 22:00 → 08:00)
            curMin >= startMin || curMin < endMin
        }
    }

    private fun trySetFilter(nm: NotificationManager, target: Int) {
        try {
            nm.setInterruptionFilter(target)
        } catch (e: SecurityException) {
            Log.w(TAG, "setInterruptionFilter denied: ${e.message}")
        }
    }

    private fun scheduleNext(ctx: Context) {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val (sh, sm) = getStart(ctx)
        val (eh, em) = getEnd(ctx)
        val nextOn = nextOccurrenceMillis(sh, sm)
        val nextOff = nextOccurrenceMillis(eh, em)
        scheduleExact(ctx, am, ACTION_DND_ON, REQ_ON, nextOn)
        scheduleExact(ctx, am, ACTION_DND_OFF, REQ_OFF, nextOff)
    }

    private fun scheduleExact(
        ctx: Context,
        am: AlarmManager,
        action: String,
        reqCode: Int,
        triggerAt: Long,
    ) {
        val pi = pendingIntent(ctx, action, reqCode)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !am.canScheduleExactAlarms()) {
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
            } else {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
            }
        } catch (e: SecurityException) {
            Log.w(TAG, "alarm schedule denied for $action: ${e.message}")
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
        }
    }

    private fun pendingIntent(ctx: Context, action: String, reqCode: Int): PendingIntent {
        // Explicit component — receiver does not need a manifest <action> filter
        // for these to dispatch.
        val intent = Intent(ctx, DndReceiver::class.java).apply { this.action = action }
        return PendingIntent.getBroadcast(
            ctx, reqCode, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun nextOccurrenceMillis(hour: Int, minute: Int): Long {
        val cal = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        if (cal.timeInMillis <= System.currentTimeMillis()) {
            cal.add(Calendar.DAY_OF_YEAR, 1)
        }
        return cal.timeInMillis
    }

    fun hasPolicyAccess(ctx: Context): Boolean {
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        return nm.isNotificationPolicyAccessGranted
    }

    /**
     * Mark only the allowlisted Vessences notification channels as bypassDnd.
     * Idempotent. Note: 3rd-party apps can only set bypassDnd if the user has
     * granted ACCESS_NOTIFICATION_POLICY; this is why we call this on every
     * apply — once permission is granted, the flag will stick.
     */
    fun ensureBypassDnd(ctx: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        if (!hasPolicyAccess(ctx)) return
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        for (id in BYPASS_DND_CHANNELS) {
            val ch = nm.getNotificationChannel(id) ?: continue
            if (!ch.canBypassDnd()) {
                ch.setBypassDnd(true)
                nm.createNotificationChannel(ch)
            }
        }
    }

    private fun prefs(ctx: Context) =
        ctx.getSharedPreferences(Constants.PREFS_NAME, Context.MODE_PRIVATE)
}

/**
 * Receives DND_ON / DND_OFF / BOOT_COMPLETED / TIME_SET / TIMEZONE_CHANGED.
 * On each event, applies the correct interruption filter for the current time
 * and re-arms the next pair of alarms.
 */
class DndReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val ctx = context.applicationContext
        if (!DndScheduler.isEnabled(ctx)) {
            // Edge case: user disabled feature between scheduling and firing.
            DndScheduler.cancelAll(ctx)
            return
        }
        // applyAndSchedule reads current time and picks ON or OFF — handles
        // both DND_ON and DND_OFF actions, plus reboot, time-change and
        // timezone-change recovery.
        DndScheduler.applyAndSchedule(ctx)
    }
}
