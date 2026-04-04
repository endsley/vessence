package com.vessences.android.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector

enum class NavTab(val label: String, val icon: ImageVector, val route: String) {
    HOME("Home", Icons.Default.Home, "home"),
    JANE("Jane", Icons.Default.Psychology, "jane"),
    ESSENCES("Essences", Icons.Default.AutoAwesome, "essences"),
    SETTINGS("Settings", Icons.Default.Settings, "settings"),
}

private val NavBarBackground = Color(0xFF0F172A)
private val SelectedColor = Color(0xFFA855F7)
private val UnselectedColor = Color(0xFF64748B)

@Composable
fun BottomNavBar(
    currentRoute: String,
    onTabSelected: (NavTab) -> Unit,
) {
    NavigationBar(
        containerColor = NavBarBackground,
        contentColor = UnselectedColor,
    ) {
        NavTab.entries.forEach { tab ->
            val selected = currentRoute == tab.route
            NavigationBarItem(
                selected = selected,
                onClick = { onTabSelected(tab) },
                icon = {
                    Icon(
                        imageVector = tab.icon,
                        contentDescription = tab.label,
                    )
                },
                label = { Text(tab.label) },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = SelectedColor,
                    selectedTextColor = SelectedColor,
                    unselectedIconColor = UnselectedColor,
                    unselectedTextColor = UnselectedColor,
                    indicatorColor = Color(0xFF1E293B),
                ),
            )
        }
    }
}
