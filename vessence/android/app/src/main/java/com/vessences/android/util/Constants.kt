package com.vessences.android.util

object Constants {
    const val DEFAULT_VAULT_BASE_URL = ""  // User must configure their own URL
    const val DEFAULT_JANE_BASE_URL = ""  // User must configure their own URL
    const val USER_AGENT = "VessencesAndroid/1.0"
    const val PREFS_NAME = "vessences_prefs"
    const val PREF_SERVER_URL = "server_url"
    const val PREF_JANE_URL = "jane_url"
    const val PREF_GOOGLE_CLIENT_ID = "google_client_id"
    const val PREF_ALWAYS_LISTENING = "always_listening"
    const val PREF_TRIGGER_PHRASE = "trigger_phrase"
    const val PREF_TRIGGER_TRAINED = "trigger_trained"
    const val PREF_TRIGGER_SAMPLES_COUNT = "trigger_samples_count"
    const val DEFAULT_TRIGGER_PHRASE = "hey jane"
    const val PREF_WAKE_WORD_THRESHOLD = "wake_word_threshold"
    const val DEFAULT_WAKE_WORD_THRESHOLD = 0.8f
    const val GOOGLE_CLIENT_ID = "1001681818033-pfdvctccvqm3gcd9a8n8v2j7jiia8a06.apps.googleusercontent.com"
    const val DEFAULT_RELAY_URL = "https://relay.vessences.com"
    const val PREF_CONNECTION_MODE = "connection_mode"  // "direct" or "relay"
    const val PREF_KEEP_SCREEN_ON = "keep_screen_on"
    // Phone tools (contacts / call / SMS draft / messages.read_recent).
    // Default OFF until Phase 5 deployment; dispatcher silently drops tool
    // calls when this flag is false so Android can ship the scaffolding
    // without activating any user-visible behavior.
    const val PREF_PHONE_TOOLS_ENABLED = "phone_tools_enabled"
}
