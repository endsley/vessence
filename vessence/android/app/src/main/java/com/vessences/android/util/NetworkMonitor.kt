package com.vessences.android.util

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Singleton network-state observer for the chat client (job_076).
 *
 * Backs `TransientError` vs `OfflineError` classification:
 *  - `isOnline` — up-to-date connectivity flag for pre-flight checks.
 *  - `transport` — current active transport (WIFI / CELLULAR / ETHERNET / NONE).
 *  - `transitionCount` — monotonically increments whenever the active
 *    transport type changes. ChatRepository snapshots this when a call
 *    starts; if it's higher when the call throws `UnknownHostException`,
 *    a network switch (e.g. WIFI→CELLULAR) happened and the error is
 *    treated as transient. Otherwise it's fatal (persistent DNS failure).
 *
 * Pattern adapted from Now-in-Android's `ConnectivityManagerNetworkMonitor`.
 */
object NetworkMonitor {

    enum class Transport { WIFI, CELLULAR, ETHERNET, OTHER, NONE }

    private var initialized = false
    private var cm: ConnectivityManager? = null

    private val _isOnline = MutableStateFlow(false)
    val isOnline: StateFlow<Boolean> = _isOnline.asStateFlow()

    private val _transport = MutableStateFlow(Transport.NONE)
    val transport: StateFlow<Transport> = _transport.asStateFlow()

    private val _transitionCount = MutableStateFlow(0L)
    val transitionCount: StateFlow<Long> = _transitionCount.asStateFlow()

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) = recompute()
        override fun onLost(network: Network) = recompute()
        override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) = recompute()
    }

    /**
     * Must be called once at app startup (e.g. from Application.onCreate).
     * Safe to call multiple times; subsequent calls are no-ops.
     */
    fun init(context: Context) {
        if (initialized) return
        initialized = true
        cm = context.applicationContext.getSystemService(ConnectivityManager::class.java)
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .addCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
            .build()
        try {
            cm?.registerNetworkCallback(request, callback)
        } catch (_: SecurityException) {
            // Permission missing — fall back to "always online" to avoid false offline errors.
            _isOnline.value = true
        }
        recompute()
    }

    private fun recompute() {
        val conn = cm ?: return
        val active = conn.activeNetwork
        if (active == null) {
            if (_transport.value != Transport.NONE) bumpTransition()
            _isOnline.value = false
            _transport.value = Transport.NONE
            return
        }
        val caps = conn.getNetworkCapabilities(active)
        val online = caps != null &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        val newTransport = when {
            caps == null -> Transport.NONE
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> Transport.WIFI
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> Transport.CELLULAR
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> Transport.ETHERNET
            else -> Transport.OTHER
        }
        if (newTransport != _transport.value) bumpTransition()
        _isOnline.value = online
        _transport.value = newTransport
    }

    private fun bumpTransition() {
        _transitionCount.value = _transitionCount.value + 1
    }
}
