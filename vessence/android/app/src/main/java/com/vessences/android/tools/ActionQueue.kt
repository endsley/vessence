package com.vessences.android.tools

import android.content.Context
import android.content.Intent
import android.util.Log
import com.vessences.android.voice.AndroidTtsManager
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Serializes tool-related TTS and external-intent launches so handlers don't
 * fight over the audio channel or stack competing dialogs / activities.
 *
 * Two mutexes:
 *  - [toolMutex]  — guards tool speech + tool intent launches. Tool speech has
 *                   priority and can interrupt an in-flight chat TTS stream.
 *  - [chatFence]  — reserved for future use if chat TTS ever needs to wait on
 *                   a tool handler. v1 unused.
 *
 * This class is cheap to create; every ClientToolDispatcher instance owns one.
 * It does NOT own the [AndroidTtsManager] — it borrows the one already created
 * by ChatViewModel (passed in via [attachTts]).
 */
class ActionQueue {
    private val toolMutex = Mutex()

    @Volatile
    private var tts: AndroidTtsManager? = null

    /**
     * Wire this queue to the same TTS manager the chat view model already uses.
     * Called once at dispatcher init time by the ChatViewModel wrapper.
     */
    fun attachTts(manager: AndroidTtsManager) {
        tts = manager
    }

    /**
     * Speak [text] with tool priority. Interrupts any in-flight chat TTS by
     * calling [AndroidTtsManager.stop] before the new utterance. Blocks until
     * the utterance is queued (AndroidTtsManager itself handles the async
     * playback lifecycle).
     */
    suspend fun speak(text: String) {
        toolMutex.withLock {
            val manager = tts
            if (manager == null) {
                Log.w(TAG, "speak called before TTS was attached: '$text'")
                return@withLock
            }
            // Tool speech interrupts any chat TTS mid-stream.
            manager.stop()
            manager.speak(text)
        }
    }

    /**
     * Launch an activity as a fresh task. Serialized with speech so the
     * countdown TTS can finish before the call intent fires.
     *
     * Returns the caught exception (null on success) so callers can
     * distinguish a successful dispatch from a silent failure. The previous
     * version caught-and-logged, letting handlers report Completed when the
     * call never actually reached the dialer.
     */
    suspend fun startActivity(ctx: Context, intent: Intent): Throwable? {
        return toolMutex.withLock {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            try {
                ctx.startActivity(intent)
                null
            } catch (e: Throwable) {
                Log.e(TAG, "Failed to start activity for intent $intent", e)
                e
            }
        }
    }

    /**
     * Acquire and immediately release the tool mutex. Useful as a fence to
     * wait for any in-flight tool action to complete before proceeding.
     */
    suspend fun fence() {
        toolMutex.withLock { /* no-op */ }
    }

    companion object {
        private const val TAG = "ActionQueue"
    }
}
