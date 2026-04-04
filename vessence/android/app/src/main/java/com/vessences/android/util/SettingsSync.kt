package com.vessences.android.util

import android.content.Context
import android.util.Log
import com.vessences.android.data.api.ApiClient
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Syncs app settings between the server and local SharedPreferences.
 *
 * On startup: pulls server settings and merges into local prefs.
 * Jane can update settings server-side via PUT /api/app/settings,
 * and the app picks them up on next launch.
 */
object SettingsSync {
    private const val TAG = "SettingsSync"
    private const val PREFS_NAME = "synced_settings"
    private val gson = Gson()

    /**
     * Pull settings from server and merge into local prefs.
     * Server values override local for keys that exist on server.
     * Local-only keys are preserved.
     */
    suspend fun pullFromServer(context: Context): Map<String, Any> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${ApiClient.getJaneBaseUrl()}/api/app/settings")
                .get()
                .build()
            val response = ApiClient.getOkHttpClient().newCall(request).execute()
            if (!response.isSuccessful) {
                response.close()
                return@withContext emptyMap()
            }
            val body = response.body?.string() ?: "{}"
            response.close()

            val type = object : TypeToken<Map<String, Any>>() {}.type
            val serverSettings: Map<String, Any> = gson.fromJson(body, type)

            // Merge into local prefs
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val editor = prefs.edit()
            for ((key, value) in serverSettings) {
                when (value) {
                    is Boolean -> editor.putBoolean(key, value)
                    is String -> editor.putString(key, value)
                    is Number -> {
                        if (value.toDouble() == value.toLong().toDouble()) {
                            editor.putLong(key, value.toLong())
                        } else {
                            editor.putFloat(key, value.toFloat())
                        }
                    }
                }
            }
            editor.apply()
            Log.d(TAG, "Synced ${serverSettings.size} settings from server")
            serverSettings
        } catch (e: Exception) {
            Log.w(TAG, "Settings sync failed: ${e.message}")
            emptyMap()
        }
    }

    /**
     * Push a local setting change to the server.
     */
    suspend fun pushToServer(key: String, value: Any) = withContext(Dispatchers.IO) {
        try {
            val body = gson.toJson(mapOf(key to value))
            val request = Request.Builder()
                .url("${ApiClient.getJaneBaseUrl()}/api/app/settings")
                .put(body.toRequestBody("application/json".toMediaType()))
                .build()
            ApiClient.getOkHttpClient().newCall(request).execute().close()
            Log.d(TAG, "Pushed setting: $key = $value")
        } catch (e: Exception) {
            Log.w(TAG, "Push setting failed: ${e.message}")
        }
    }

    /**
     * Read a synced setting locally. Falls back to default if not set.
     */
    fun getString(context: Context, key: String, default: String = ""): String =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).getString(key, default) ?: default

    fun getBoolean(context: Context, key: String, default: Boolean = false): Boolean =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).getBoolean(key, default)

    fun getLong(context: Context, key: String, default: Long = 0): Long =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).getLong(key, default)
}
