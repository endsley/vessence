package com.vessences.android

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.vessences.android.data.repository.AuthState
import com.vessences.android.ui.auth.LoginScreen
import com.vessences.android.ui.auth.LoginViewModel
import com.vessences.android.ui.chat.JaneChatScreen
import com.vessences.android.ui.components.NavTab
import com.vessences.android.ui.essences.EssencesScreen
import com.vessences.android.ui.home.HomeScreen
import com.vessences.android.ui.music.MusicScreen
import com.vessences.android.ui.settings.SettingsScreen
import com.vessences.android.ui.vault.VaultScreen
import com.vessences.android.ui.voice.TriggerWordTrainingScreen
import com.vessences.android.ui.briefing.BriefingScreen
import com.vessences.android.ui.worklog.WorkLogScreen

private val SlateBackground = Color(0xFF0F172A)
private val Violet500 = Color(0xFFA855F7)

@Composable
fun VessencesApp(loginViewModel: LoginViewModel = viewModel()) {
    val authState by loginViewModel.authState.collectAsState()

    when (authState) {
        AuthState.LOADING -> {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(SlateBackground),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator(color = Violet500)
            }
        }
        AuthState.UNAUTHENTICATED -> {
            LoginScreen(viewModel = loginViewModel)
        }
        AuthState.AUTHENTICATED -> {
            AuthenticatedApp(loginViewModel = loginViewModel)
        }
    }
}

@Composable
private fun AuthenticatedApp(loginViewModel: LoginViewModel) {
    val navController = rememberNavController()

    Scaffold(
        containerColor = SlateBackground,
    ) { paddingValues ->
        NavHost(
            navController = navController,
            startDestination = NavTab.HOME.route,
            modifier = Modifier.padding(paddingValues),
        ) {
            composable(NavTab.HOME.route) {
                HomeScreen(
                    onNavigateToJane = {
                        navController.navigate(NavTab.JANE.route) {
                            launchSingleTop = true
                        }
                    },
                    onNavigateToEssenceView = { essenceName ->
                        navController.navigate("essence_view/$essenceName") {
                            launchSingleTop = true
                        }
                    },
                    onNavigateToSettings = {
                        navController.navigate(NavTab.SETTINGS.route) {
                            launchSingleTop = true
                        }
                    },
                )
            }
            composable(NavTab.JANE.route) {
                JaneChatScreen(
                    onNavigateToEssenceView = { essenceName ->
                        navController.navigate("essence_view/$essenceName")
                    },
                    onBack = { navController.popBackStack() },
                )
            }
            composable(NavTab.ESSENCES.route) {
                EssencesScreen(
                    onOpenEssenceView = { essenceName ->
                        navController.navigate("essence_view/$essenceName")
                    },
                )
            }
            composable(NavTab.SETTINGS.route) {
                SettingsScreen(
                    onLogout = { loginViewModel.logout() },
                    onNavigateToTriggerTraining = {
                        navController.navigate("trigger_training") {
                            launchSingleTop = true
                        }
                    },
                )
            }
            composable("trigger_training") {
                TriggerWordTrainingScreen(
                    onComplete = { navController.popBackStack() },
                    onBack = { navController.popBackStack() },
                )
            }
            composable("essence_view/{essenceName}") { backStackEntry ->
                val essenceName = backStackEntry.arguments?.getString("essenceName") ?: ""
                EssenceViewRouter(
                    essenceName = essenceName,
                    onBack = { navController.popBackStack() },
                )
            }
        }
    }
}

@Composable
private fun EssenceViewRouter(
    essenceName: String,
    onBack: () -> Unit,
) {
    when (essenceName) {
        "Life Librarian" -> VaultScreen(onBack = onBack)
        "Music Playlist" -> MusicScreen(onBack = onBack)
        "Work Log" -> WorkLogScreen(onBack = onBack)
        "Daily Briefing" -> BriefingScreen(onBack = onBack)
        else -> EssencePlaceholderView(essenceName = essenceName, onBack = onBack)
    }
}

@Composable
private fun EssencePlaceholderView(
    essenceName: String,
    onBack: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SlateBackground),
    ) {
        Surface(color = SlateBackground) {
            Row(
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "Back",
                        tint = Color.White,
                    )
                }
                Text(
                    text = essenceName,
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = "Coming soon",
                color = Color(0xFF64748B),
                fontSize = 16.sp,
            )
        }
    }
}
