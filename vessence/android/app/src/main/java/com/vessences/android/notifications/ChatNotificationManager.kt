package com.vessences.android.notifications

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.vessences.android.MainActivity
import com.vessences.android.R

class ChatNotificationManager(private val context: Context) {
    private val appContext = context.applicationContext
    private val notificationManager = NotificationManagerCompat.from(appContext)
    private var lastNotificationTime = 0L
    private val NOTIFICATION_COOLDOWN_MS = 5 * 60 * 1000L  // 5 minutes

    // isAppInForeground is in the companion object below

    fun ensureChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return

        val systemNotificationManager =
            appContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        val soundUri = Settings.System.DEFAULT_NOTIFICATION_URI
        val audioAttributes = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .build()

        val channels = listOf(
            NotificationChannel(
                CHANNEL_JANE,
                "Jane Messages",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Notifications when Jane replies"
                enableVibration(true)
                setSound(soundUri, audioAttributes)
            },
            NotificationChannel(
                CHANNEL_AMBER,
                "Amber Messages",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Notifications when Amber replies"
                enableVibration(true)
                setSound(soundUri, audioAttributes)
            },
        )

        systemNotificationManager.createNotificationChannels(channels)
    }

    fun showReplyNotification(senderName: String, message: String) {
        if (message.isBlank()) return
        // Don't notify if app is in foreground — user is already looking at it
        if (isAppInForeground) return
        // Rate limit: max 1 notification per 5 minutes
        val now = System.currentTimeMillis()
        if (now - lastNotificationTime < NOTIFICATION_COOLDOWN_MS) return
        lastNotificationTime = now
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(appContext, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        val intent = Intent(appContext, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("open_chat", senderName.lowercase())
        }
        val pendingIntent = PendingIntent.getActivity(
            appContext,
            senderName.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val channelId = if (senderName.equals("Jane", ignoreCase = true)) CHANNEL_JANE else CHANNEL_AMBER
        val notificationId = if (channelId == CHANNEL_JANE) NOTIFICATION_ID_JANE else NOTIFICATION_ID_AMBER

        val notification = NotificationCompat.Builder(appContext, channelId)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("$senderName sent you a message")
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .build()

        notificationManager.notify(notificationId, notification)
    }

    companion object {
        private const val CHANNEL_JANE = "chat_jane_messages"
        private const val CHANNEL_AMBER = "chat_amber_messages"
        private const val NOTIFICATION_ID_JANE = 1001
        private const val NOTIFICATION_ID_AMBER = 1002

        /** Set to true when the app is in the foreground. */
        @Volatile
        var isAppInForeground = false
    }
}
