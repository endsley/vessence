package com.vessences.android.util

import android.content.Context
import android.content.SharedPreferences
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl

class CookieStore(context: Context) : CookieJar {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("vessences_cookies", Context.MODE_PRIVATE)

    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val editor = prefs.edit()
        val key = url.host
        val existing = loadForHost(key).toMutableMap()
        for (cookie in cookies) {
            existing[cookie.name] = cookie.toString()
        }
        editor.putStringSet(key, existing.entries.map { "${it.key}=${it.value}" }.toSet())
        editor.apply()
    }

    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val raw = prefs.getStringSet(url.host, emptySet()) ?: emptySet()
        return raw.mapNotNull { entry ->
            val cookieStr = entry.substringAfter("=", "")
            if (cookieStr.isNotEmpty()) Cookie.parse(url, cookieStr) else null
        }
    }

    private fun loadForHost(host: String): Map<String, String> {
        val raw = prefs.getStringSet(host, emptySet()) ?: emptySet()
        return raw.associate { entry ->
            val name = entry.substringBefore("=")
            val value = entry.substringAfter("=", "")
            name to value
        }
    }

    fun clear() {
        prefs.edit().clear().apply()
    }
}
