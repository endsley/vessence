package com.vessences.android.photos

import android.content.Context
import com.vessences.android.util.Constants

class CameraSyncSettings(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(
        Constants.PREFS_NAME,
        Context.MODE_PRIVATE,
    )

    fun isEnabled(): Boolean = prefs.getBoolean(Constants.PREF_CAMERA_SYNC_ENABLED, true)

    fun setEnabled(enabled: Boolean) {
        prefs.edit().putBoolean(Constants.PREF_CAMERA_SYNC_ENABLED, enabled).apply()
    }

    fun isWifiOnly(): Boolean = prefs.getBoolean(Constants.PREF_CAMERA_SYNC_WIFI_ONLY, true)

    fun setWifiOnly(wifiOnly: Boolean) {
        prefs.edit().putBoolean(Constants.PREF_CAMERA_SYNC_WIFI_ONLY, wifiOnly).apply()
    }

    fun syncedKeys(): Set<String> {
        return prefs.getStringSet(Constants.PREF_CAMERA_SYNC_KEYS, emptySet()).orEmpty().toSet()
    }

    fun markSynced(key: String) {
        val next = syncedKeys().toMutableSet()
        next.add(key)
        prefs.edit().putStringSet(Constants.PREF_CAMERA_SYNC_KEYS, next).apply()
    }

    fun lastRunMillis(): Long = prefs.getLong(Constants.PREF_CAMERA_SYNC_LAST_RUN, 0L)

    fun lastUploaded(): Int = prefs.getInt(Constants.PREF_CAMERA_SYNC_LAST_UPLOADED, 0)

    fun lastFailed(): Int = prefs.getInt(Constants.PREF_CAMERA_SYNC_LAST_FAILED, 0)

    fun lastMessage(): String = prefs.getString(Constants.PREF_CAMERA_SYNC_LAST_MESSAGE, "") ?: ""

    fun recordResult(result: CameraSyncResult) {
        prefs.edit()
            .putLong(Constants.PREF_CAMERA_SYNC_LAST_RUN, System.currentTimeMillis())
            .putInt(Constants.PREF_CAMERA_SYNC_LAST_UPLOADED, result.uploaded)
            .putInt(Constants.PREF_CAMERA_SYNC_LAST_FAILED, result.failed)
            .putString(Constants.PREF_CAMERA_SYNC_LAST_MESSAGE, result.message)
            .apply()
    }
}
