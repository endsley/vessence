package com.vessences.android.ui.settings

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.vessences.android.ui.theme.ThemePreferences

private val SlateBg = Color(0xFF0F172A)
private val SlateCard = Color(0xFF1E293B)
private val Violet500 = Color(0xFFA855F7)
private val SlateText = Color(0xFF94A3B8)

@Composable
fun SettingsScreen(
    onLogout: () -> Unit,
    onNavigateToTriggerTraining: (() -> Unit)? = null,
    viewModel: SettingsViewModel = viewModel(
        factory = SettingsViewModelFactory(
            appContext = LocalContext.current.applicationContext,
        )
    ),
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    var pendingAlwaysListeningEnable by remember { mutableStateOf(false) }
    val recordAudioLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted && pendingAlwaysListeningEnable) {
            if (!state.triggerTrained && onNavigateToTriggerTraining != null) {
                onNavigateToTriggerTraining()
            } else {
                viewModel.setAlwaysListeningEnabled(true)
            }
        }
        pendingAlwaysListeningEnable = false
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBg)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(
                "Settings",
                color = Color.White,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
            )
        }

        // Theme
        item {
            Text(
                "Theme",
                color = Color.White,
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        item {
            val isDark by ThemePreferences.isDarkMode.collectAsState()
            Surface(
                shape = RoundedCornerShape(12.dp),
                color = SlateCard,
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Default.DarkMode,
                        contentDescription = null,
                        tint = Violet500,
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            if (isDark) "Dark Mode" else "Light Mode",
                            color = Color.White,
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                        )
                        Text(
                            "Toggle between dark and light appearance",
                            color = SlateText,
                            fontSize = 12.sp,
                        )
                    }
                    Switch(
                        checked = isDark,
                        onCheckedChange = { dark ->
                            ThemePreferences.setDarkMode(context, dark)
                        },
                    )
                }
            }
        }

        // Always-listening voice mode
        item {
            Surface(
                shape = RoundedCornerShape(12.dp),
                color = SlateCard,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            Icons.Default.Mic,
                            contentDescription = null,
                            tint = Violet500,
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                "Always-listening voice mode",
                                color = Color.White,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 14.sp,
                            )
                            Text(
                                "Listen for your trigger word in the background",
                                color = SlateText,
                                fontSize = 12.sp,
                            )
                        }
                        Switch(
                            checked = state.alwaysListeningEnabled,
                            onCheckedChange = { enabled ->
                                if (enabled) {
                                    val hasMicPermission = ContextCompat.checkSelfPermission(
                                        context,
                                        Manifest.permission.RECORD_AUDIO,
                                    ) == PackageManager.PERMISSION_GRANTED
                                    if (!hasMicPermission) {
                                        pendingAlwaysListeningEnable = true
                                        recordAudioLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                    } else if (!state.triggerTrained && onNavigateToTriggerTraining != null) {
                                        onNavigateToTriggerTraining()
                                    } else {
                                        viewModel.setAlwaysListeningEnabled(true)
                                    }
                                } else {
                                    viewModel.setAlwaysListeningEnabled(false)
                                }
                            },
                        )
                    }

                    // Show trigger phrase and controls when enabled or trained
                    if (state.triggerTrained || state.alwaysListeningEnabled) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Divider(color = Color(0xFF334155))
                        Spacer(modifier = Modifier.height(8.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                "Trigger: \"${state.triggerPhrase}\"",
                                color = SlateText,
                                fontSize = 13.sp,
                                modifier = Modifier.weight(1f),
                            )
                            if (onNavigateToTriggerTraining != null) {
                                // Edit link
                                Text(
                                    "Edit",
                                    color = Violet500,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    modifier = Modifier
                                        .clickable { onNavigateToTriggerTraining() }
                                        .padding(horizontal = 8.dp, vertical = 4.dp),
                                )
                            }
                        }

                        if (state.triggerTrained && onNavigateToTriggerTraining != null) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Row(
                                modifier = Modifier
                                    .clickable { onNavigateToTriggerTraining() }
                                    .padding(vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(
                                    Icons.Default.Refresh,
                                    contentDescription = null,
                                    tint = SlateText,
                                    modifier = Modifier.size(16.dp),
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    "Retrain trigger word",
                                    color = SlateText,
                                    fontSize = 12.sp,
                                )
                            }
                        }
                    }
                }
            }
        }

        // Trusted Devices
        item {
            Text(
                "Trusted Devices",
                color = Color.White,
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        if (state.devices.isEmpty()) {
            item {
                Text("No trusted devices", color = SlateText, fontSize = 14.sp)
            }
        } else {
            items(state.devices) { device ->
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = SlateCard,
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                device.label.ifEmpty { "Unknown device" },
                                color = Color.White,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 14.sp,
                            )
                            Text(
                                "First seen: ${device.firstSeen}",
                                color = SlateText,
                                fontSize = 12.sp,
                            )
                        }
                        IconButton(onClick = { viewModel.revokeDevice(device.id) }) {
                            Icon(Icons.Default.Delete, "Revoke", tint = Color(0xFFF87171))
                        }
                    }
                }
            }
        }

        // Shares
        item {
            Text(
                "Active Shares",
                color = Color.White,
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        if (state.shares.isEmpty()) {
            item {
                Text("No active shares", color = SlateText, fontSize = 14.sp)
            }
        } else {
            items(state.shares) { share ->
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = SlateCard,
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                share.path.ifEmpty { "/" },
                                color = Color.White,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 14.sp,
                            )
                            Text(
                                "Code: ${share.code}",
                                color = SlateText,
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace,
                            )
                            Text(
                                "For: ${share.createdFor} · ${share.accessCount} accesses",
                                color = SlateText,
                                fontSize = 12.sp,
                            )
                        }
                        IconButton(onClick = { viewModel.revokeShare(share.id) }) {
                            Icon(Icons.Default.Delete, "Revoke", tint = Color(0xFFF87171))
                        }
                    }
                }
            }
        }

        // Logout
        item {
            Spacer(modifier = Modifier.height(24.dp))
            Button(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFF991B1B),
                    contentColor = Color.White,
                ),
                shape = RoundedCornerShape(12.dp),
            ) {
                Icon(Icons.Default.Logout, "Logout")
                Spacer(modifier = Modifier.width(8.dp))
                Text("Sign Out")
            }
        }
    }
}
