package com.vessences.android.ui.chat

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.MutableState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File

private val SlateCard = Color(0xFF1E293B)
private val SlateMuted = Color(0xFF94A3B8)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AttachmentSheet(
    showSheet: Boolean,
    onDismiss: () -> Unit,
    aiColor: Color,
    ttsEnabled: MutableState<Boolean>,
    autoListenEnabled: MutableState<Boolean>,
    attachedFileUri: MutableState<Uri?>,
    attachedFileName: MutableState<String?>,
    cameraPhotoUri: MutableState<Uri?>,
    isSending: Boolean = false,
    onCancel: (() -> Unit)? = null,
) {
    val context = LocalContext.current

    // File picker launcher
    val filePickerLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            // Take persistent read permission so the URI stays valid during upload
            try {
                context.contentResolver.takePersistableUriPermission(
                    uri, Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
            } catch (_: SecurityException) {
                // Not all providers support persistable permissions — that's OK,
                // the temporary grant from the picker result is usually enough.
            }
            attachedFileUri.value = uri
            // Resolve a human-readable filename from the content provider
            var name = uri.lastPathSegment ?: "file"
            try {
                context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) {
                        val idx = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                        if (idx >= 0) name = cursor.getString(idx) ?: name
                    }
                }
            } catch (_: Exception) {}
            attachedFileName.value = name
        }
    }

    // Camera launcher
    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { success: Boolean ->
        if (success && cameraPhotoUri.value != null) {
            attachedFileUri.value = cameraPhotoUri.value
            attachedFileName.value = "photo.jpg"
        }
    }

    // Camera permission launcher
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            val photoFile = File.createTempFile("photo_", ".jpg", context.cacheDir)
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", photoFile)
            cameraPhotoUri.value = uri
            cameraLauncher.launch(uri)
        }
    }

    if (showSheet) {
        ModalBottomSheet(
            onDismissRequest = onDismiss,
            containerColor = SlateCard,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 32.dp),
            ) {
                Text(
                    text = "Attach",
                    color = Color.White,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                )
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            onDismiss()
                            filePickerLauncher.launch("*/*")
                        },
                    color = Color.Transparent,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Default.Description, contentDescription = null, tint = aiColor)
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("Choose file", color = Color.White, fontSize = 16.sp)
                    }
                }
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            onDismiss()
                            val hasCamPerm = ContextCompat.checkSelfPermission(
                                context, Manifest.permission.CAMERA
                            ) == PackageManager.PERMISSION_GRANTED
                            if (hasCamPerm) {
                                val photoFile = File.createTempFile("photo_", ".jpg", context.cacheDir)
                                val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", photoFile)
                                cameraPhotoUri.value = uri
                                cameraLauncher.launch(uri)
                            } else {
                                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        },
                    color = Color.Transparent,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Default.CameraAlt, contentDescription = null, tint = aiColor)
                        Spacer(modifier = Modifier.width(12.dp))
                        Text("Take photo", color = Color.White, fontSize = 16.sp)
                    }
                }
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            ttsEnabled.value = !ttsEnabled.value
                            onDismiss()
                        },
                    color = Color.Transparent,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.VolumeUp,
                            contentDescription = null,
                            tint = if (ttsEnabled.value) Color(0xFF22C55E) else aiColor,
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = if (ttsEnabled.value) "Voice response (on)" else "Voice response",
                            color = Color.White,
                            fontSize = 16.sp,
                        )
                    }
                }
                
                // Only show auto-listen option if TTS is enabled
                if (ttsEnabled.value) {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                autoListenEnabled.value = !autoListenEnabled.value
                                // Don't dismiss, let them see it change
                            },
                        color = Color.Transparent,
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(
                                if (autoListenEnabled.value) Icons.Default.Mic else Icons.Default.MicOff,
                                contentDescription = null,
                                tint = if (autoListenEnabled.value) Color(0xFF22C55E) else SlateMuted,
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = if (autoListenEnabled.value) "Auto-listen after speaking (on)" else "Auto-listen after speaking (off)",
                                color = Color.White,
                                fontSize = 16.sp,
                            )
                        }
                    }
                }
                
                // Cancel response option — only shown while Jane is responding
                if (isSending && onCancel != null) {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                onCancel()
                                onDismiss()
                            },
                        color = Color.Transparent,
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFEF4444))
                            Spacer(modifier = Modifier.width(12.dp))
                            Text("Cancel response", color = Color(0xFFEF4444), fontSize = 16.sp)
                        }
                    }
                }
            }
        }
    }
}
