package com.vessences.android.ui.auth

import android.app.Application
import android.content.Context
import android.content.Intent
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.vessences.android.DiagnosticReporter
import com.vessences.android.data.repository.AuthRepository
import com.vessences.android.data.repository.AuthState
import com.vessences.android.data.repository.LegacySignInFallbackNeeded
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch

class LoginViewModel(application: Application) : AndroidViewModel(application) {
    val authRepository = AuthRepository(application)
    val authState: StateFlow<AuthState> = authRepository.authState

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    private val _isSigningIn = MutableStateFlow(false)
    val isSigningIn: StateFlow<Boolean> = _isSigningIn

    // Emits when Credential Manager is unavailable — screen should launch this intent
    private val _legacySignInIntent = MutableSharedFlow<Intent>(extraBufferCapacity = 1)
    val legacySignInIntent: SharedFlow<Intent> = _legacySignInIntent.asSharedFlow()

    init {
        viewModelScope.launch {
            authRepository.checkAuth()
        }
    }

    fun signIn(activityContext: Context) {
        viewModelScope.launch {
            _isSigningIn.value = true
            _error.value = null
            try {
                val result = authRepository.signInWithGoogle(activityContext)
                result.onFailure { e ->
                    _error.value = e.message ?: "Sign-in failed"
                }
            } catch (e: LegacySignInFallbackNeeded) {
                // Credential Manager not available — fall back to legacy Google Sign-In
                DiagnosticReporter.report("auth", "auth[legacy_launch]", mapOf(
                    "reason" to e.message,
                ))
                val intent = authRepository.getLegacySignInIntent(activityContext)
                val emitted = _legacySignInIntent.tryEmit(intent)
                DiagnosticReporter.report("auth", "auth[legacy_intent_emitted]", mapOf(
                    "emitted" to emitted,
                ))
                if (!emitted) {
                    _isSigningIn.value = false
                    _error.value = "Google sign-in could not start. Please try again."
                }
                // isSigningIn stays true while the legacy activity is open
                return@launch
            }
            _isSigningIn.value = false
        }
    }

    fun handleLegacyResult(data: Intent?) {
        viewModelScope.launch {
            _error.value = null
            val result = authRepository.handleLegacySignInResult(data)
            result.onFailure { e ->
                _error.value = e.message ?: "Sign-in failed"
            }
            _isSigningIn.value = false
        }
    }

    fun logout() {
        viewModelScope.launch {
            authRepository.logout()
        }
    }

    fun clearError() {
        _error.value = null
    }

    fun cancelSignIn() {
        _error.value = null
        _isSigningIn.value = false
    }
}
