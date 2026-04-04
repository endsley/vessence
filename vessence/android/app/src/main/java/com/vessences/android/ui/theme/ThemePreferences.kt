package com.vessences.android.ui.theme

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

object ThemePreferences {
    private const val PREFS_NAME = "vessence_prefs"
    private const val KEY_THEME_MODE = "theme_mode"

    private val _isDarkMode = MutableStateFlow(true)
    val isDarkMode: StateFlow<Boolean> = _isDarkMode

    fun init(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        _isDarkMode.value = prefs.getString(KEY_THEME_MODE, "dark") == "dark"
    }

    fun toggleTheme(context: Context) {
        val newIsDark = !_isDarkMode.value
        _isDarkMode.value = newIsDark
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_THEME_MODE, if (newIsDark) "dark" else "light")
            .apply()
    }

    fun setDarkMode(context: Context, isDark: Boolean) {
        _isDarkMode.value = isDark
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_THEME_MODE, if (isDark) "dark" else "light")
            .apply()
    }
}
