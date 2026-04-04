package com.vessences.android.ui.auth

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.vessences.android.data.repository.AuthRepository
import com.vessences.android.data.repository.AuthState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class LoginViewModel(application: Application) : AndroidViewModel(application) {
    val authRepository = AuthRepository(application)
    val authState: StateFlow<AuthState> = authRepository.authState

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    private val _isSigningIn = MutableStateFlow(false)
    val isSigningIn: StateFlow<Boolean> = _isSigningIn

    init {
        viewModelScope.launch {
            authRepository.checkAuth()
        }
    }

    fun signIn(activityContext: Context) {
        viewModelScope.launch {
            _isSigningIn.value = true
            _error.value = null
            val result = authRepository.signInWithGoogle(activityContext)
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
}
