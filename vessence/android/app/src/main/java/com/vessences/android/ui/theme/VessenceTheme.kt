package com.vessences.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.Color

private val Violet500 = Color(0xFFA855F7)
private val Violet700 = Color(0xFF7C3AED)
private val Violet300 = Color(0xFFC084FC)

private val VessenceDarkColorScheme = darkColorScheme(
    primary = Violet500,
    onPrimary = Color.White,
    primaryContainer = Violet700,
    onPrimaryContainer = Color.White,
    secondary = Violet300,
    onSecondary = Color.Black,
    background = Color(0xFF0F172A),
    onBackground = Color.White,
    surface = Color(0xFF1E293B),
    onSurface = Color.White,
    surfaceVariant = Color(0xFF334155),
    onSurfaceVariant = Color(0xFF94A3B8),
)

private val VessenceLightColorScheme = lightColorScheme(
    primary = Violet700,
    onPrimary = Color.White,
    primaryContainer = Violet300,
    onPrimaryContainer = Color.Black,
    secondary = Violet500,
    onSecondary = Color.White,
    background = Color(0xFFF8FAFC),
    onBackground = Color(0xFF0F172A),
    surface = Color.White,
    onSurface = Color(0xFF0F172A),
    surfaceVariant = Color(0xFFE2E8F0),
    onSurfaceVariant = Color(0xFF475569),
)

@Composable
fun VessenceTheme(
    content: @Composable () -> Unit,
) {
    val isDark by ThemePreferences.isDarkMode.collectAsState()

    val colorScheme = if (isDark) VessenceDarkColorScheme else VessenceLightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        content = content,
    )
}
