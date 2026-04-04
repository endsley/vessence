package com.vessences.android.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import java.util.Locale

/**
 * Stage 2 wake word verifier — uses Android's SpeechRecognizer headlessly
 * (no popup) to transcribe the last ~1 second of audio and check if it
 * contains "jane" (or common Whisper misheard variants).
 *
 * Called when Stage 1 (OpenWakeWord DNN) fires. If the transcript
 * doesn't contain the wake word, the trigger is suppressed as a false positive.
 */
object WakeWordVerifier {
    private const val TAG = "WakeWordVerify"

    // Whisper and Google STT sometimes mishear "Jane" as these
    private val WAKE_WORD_VARIANTS = setOf(
        "jane", "james", "jayne", "jain", "jeanne",
        "hey jane", "hey james", "hey jayne",
    )

    interface VerificationCallback {
        fun onVerified(transcript: String)
        fun onRejected(transcript: String)
        fun onError(errorMessage: String)
    }

    /**
     * Start headless speech recognition to verify the wake word.
     * The recognizer listens for ~2 seconds and returns the transcript.
     */
    fun verify(context: Context, callback: VerificationCallback) {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.w(TAG, "Speech recognition not available — accepting trigger")
            callback.onVerified("(recognition unavailable)")
            return
        }

        val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            // Short listening window — we just need to catch the tail of "hey jane"
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1000L)
        }

        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val transcript = matches?.firstOrNull()?.lowercase() ?: ""
                Log.i(TAG, "Transcript: '$transcript'")

                val verified = WAKE_WORD_VARIANTS.any { it in transcript }
                if (verified) {
                    Log.i(TAG, "✅ Wake word VERIFIED in transcript")
                    callback.onVerified(transcript)
                } else {
                    Log.i(TAG, "❌ Wake word NOT found in transcript — false positive")
                    callback.onRejected(transcript)
                }
                recognizer.destroy()
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val partial = matches?.firstOrNull()?.lowercase() ?: ""
                if (partial.isNotBlank()) {
                    Log.d(TAG, "Partial: '$partial'")
                    // Early accept if we already see the wake word
                    if (WAKE_WORD_VARIANTS.any { it in partial }) {
                        Log.i(TAG, "✅ Early verify from partial: '$partial'")
                        callback.onVerified(partial)
                        recognizer.stopListening()
                        recognizer.destroy()
                    }
                }
            }

            override fun onError(error: Int) {
                val msg = when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH -> "no match"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "speech timeout"
                    SpeechRecognizer.ERROR_AUDIO -> "audio error"
                    SpeechRecognizer.ERROR_NETWORK -> "network error"
                    else -> "error $error"
                }
                Log.w(TAG, "Recognition error: $msg — accepting trigger (fail-open)")
                // Fail open: if recognition fails, accept the trigger
                // rather than blocking a real wake word
                callback.onVerified("(error: $msg)")
                recognizer.destroy()
            }

            override fun onReadyForSpeech(params: Bundle?) {
                Log.d(TAG, "Ready for speech")
            }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {
                Log.d(TAG, "End of speech")
            }
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        Log.i(TAG, "Starting headless recognition for verification...")
        recognizer.startListening(intent)
    }
}
