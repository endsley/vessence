package com.vessences.android.ui.chat

import java.util.Locale

/**
 * Shared end-of-conversation phrase detection.
 * Used by both ChatInputRow (mic button STT) and VoiceController (auto-listen STT).
 */
object EndPhraseDetector {

    private val END_PHRASES = listOf(
        // Direct end statements
        "we're done", "we are done", "were done",
        "ok we're done", "ok we are done", "okay we're done", "okay we are done",
        "ok were done", "okay were done",
        "i'm done", "i am done", "im done",
        "done now", "i'm done now", "i am done now", "im done now",
        "ok done", "okay done", "alright done", "all done",
        "that's all", "that is all", "ok that's all", "alright that's all",
        "that's it", "that is it", "ok that's it",
        "that'll be all", "that will be all",
        "nothing else", "no more questions", "no more",
        "end conversation", "conversation over", "this conversation ends",
        "end chat", "close conversation",

        // Goodbyes
        "goodbye", "good bye", "bye", "bye bye", "bye jane", "bye now",
        "see you", "see ya", "see you later", "see ya later",
        "later", "talk to you later", "talk later", "catch you later",
        "good night", "goodnight", "night jane", "night night",
        "take care", "have a good one",
        "peace", "peace out", "adios", "ciao",

        // Stop / cancel
        "stop", "stop listening", "stop talking", "shut up",
        "be quiet", "quiet", "enough", "that's enough",
        "cancel", "dismiss", "go away", "leave me alone",
        "never mind", "nevermind", "forget it", "forget about it",
        "no thanks", "nah", "nope",

        // Thank you + end
        "thank you", "thanks", "thank you jane", "thanks jane",
        "thanks that's it", "thanks that's all", "thank you that's all",
        "thanks i'm good", "thanks i am good",
        "thanks for your help", "thank you for your help",
        "thanks for the help", "appreciate it",
        "thanks bye", "thank you bye", "thanks goodbye",

        // Informal / casual
        "ok cool", "alright cool", "sounds good we're done",
        "got it thanks", "got it bye", "perfect thanks",
        "ok great", "alright great", "awesome thanks",
        "k bye", "k thanks", "ok thanks bye",
        "roger", "roger that done", "over and out",
        "i'm good", "i am good", "all good", "we're good", "we are good",
        "no worries", "all set", "i'm all set", "i am all set",
    )

    // These only match if they are the ENTIRE message (no prefix/suffix matching)
    private val EXACT_ONLY_PHRASES = setOf("ok", "okay")

    fun isEndPhrase(text: String): Boolean {
        val normalized = text.lowercase(Locale.US).trim()
            .replace('\u2019', '\'')
            .replace('\u2018', '\'')
            .replace(".", "").replace(",", "").replace("!", "").replace("?", "")
            .replace("  ", " ").trim()
        // Check exact-only phrases first
        if (normalized in EXACT_ONLY_PHRASES) return true
        val matched = END_PHRASES.any { phrase ->
            if (phrase.length <= 5) {
                normalized == phrase || normalized.startsWith("$phrase ") || normalized.endsWith(" $phrase")
            } else {
                normalized.contains(phrase)
            }
        }
        if (!matched) {
            android.util.Log.d("EndPhrase", "NOT matched: '$normalized' (raw: '$text')")
        }
        return matched
    }
}
