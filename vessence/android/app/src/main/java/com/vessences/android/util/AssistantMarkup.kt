package com.vessences.android.util

object AssistantMarkup {
    private val spokenBlockRegex = Regex("<spoken>([\\s\\S]*?)</spoken>", RegexOption.IGNORE_CASE)
    private val spokenOpenRegex = Regex("<spoken>", RegexOption.IGNORE_CASE)
    private val spokenCloseRegex = Regex("</spoken>", RegexOption.IGNORE_CASE)
    private val visualBlockRegex = Regex("<visual>([\\s\\S]*?)</visual>", RegexOption.IGNORE_CASE)
    private val assistantTagRegex = Regex("</?(?:spoken|visual|think|thinking|artifact)>", RegexOption.IGNORE_CASE)
    private val trailingPartialAssistantTagRegex = Regex("</?(?:spoken|visual|think|thinking|artifact)[^>]*$", RegexOption.IGNORE_CASE)
    private val clientToolMarkerRegex = Regex("\\[\\[CLIENT_TOOL:[a-z][a-z0-9_.]*:\\{[\\s\\S]*?\\}\\]\\]")
    private val awaitingMarkerRegex = Regex("\\[\\[AWAITING:[A-Za-z0-9_\\-\\s]{1,200}\\]\\]", RegexOption.IGNORE_CASE)
    private val trailingPartialAwaitingMarkerRegex = Regex("\\[\\[AWAITING:[A-Za-z0-9_\\-\\s]{0,200}$", RegexOption.IGNORE_CASE)
    private val ackBlockRegex = Regex("\\[ACK\\][\\s\\S]*?\\[/ACK\\]\\s*")
    private val spokenSentenceRegex = Regex("([^.!?]+[.!?])")
    private val ttsCollapseWhitespaceRegex = Regex("\\s+")

    private const val MAX_TTS_SENTENCES = 2
    private const val MAX_TTS_CHARS = 220
    private const val MAX_TTS_WORDS = 28

    fun removeAckBlocks(text: String): String =
        text.replace(ackBlockRegex, "")

    fun removeClientToolMarkers(text: String): String =
        text.replace(clientToolMarkerRegex, "")

    fun hasOpenSpokenTag(text: String): Boolean =
        spokenOpenRegex.containsMatchIn(text)

    fun forDisplay(raw: String, trim: Boolean = true): String {
        val visibleDetail = raw
            .replace(visualBlockRegex) { it.groupValues[1] }
            .replace(spokenBlockRegex, "")
        val cleaned = stripAssistantTags(visibleDetail)
        val fallback = if (cleaned.isBlank()) forSpeech(raw, trim = false) else cleaned
        return if (trim) fallback.trim() else fallback
    }

    fun forSpeech(raw: String, trim: Boolean = true): String {
        val spokenStart = spokenOpenRegex.find(raw)
        val base = if (spokenStart != null) {
            val afterOpen = raw.substring(spokenStart.range.last + 1)
            val spokenEnd = spokenCloseRegex.find(afterOpen)
            if (spokenEnd != null) afterOpen.substring(0, spokenEnd.range.first) else afterOpen
        } else {
            raw.replace(visualBlockRegex, "")
        }
        val cleaned = stripAssistantTags(base)
        return if (trim) cleaned.trim() else cleaned
    }

    fun spokenBlock(raw: String): String? =
        spokenBlockRegex.find(raw)?.groupValues?.getOrNull(1)?.trim()?.takeIf { it.isNotBlank() }

    fun enforceSpokenLength(raw: String?): String? {
        val text = normalizeTtsText(raw)
        if (text.isBlank()) return null
        val sentences = spokenSentenceRegex.findAll(text)
            .map { it.groupValues[1].trim() }
            .filter { it.isNotBlank() }
            .toList()
        var spoken = if (sentences.isNotEmpty()) sentences.take(MAX_TTS_SENTENCES).joinToString(" ") else text
        if (spoken.isBlank()) return null
        val words = spoken.split(Regex("\\s+")).filter { it.isNotBlank() }
        if (words.size > MAX_TTS_WORDS) {
            spoken = words.take(MAX_TTS_WORDS).joinToString(" ")
        }
        if (spoken.length > MAX_TTS_CHARS) {
            spoken = spoken.take(MAX_TTS_CHARS).trim()
            val cut = spoken.lastIndexOf(" ")
            if (cut > 60) {
                spoken = spoken.substring(0, cut).trim()
            }
            spoken = if (!spoken.endsWith(".") && !spoken.endsWith("?") && !spoken.endsWith("!")) {
                "$spoken…"
            } else {
                spoken
            }
        }
        return spoken.trim()
    }

    private fun stripAssistantTags(text: String): String =
        removeTrailingPartialAwaitingMarker(text)
            .replace(assistantTagRegex, "")
            .replace(trailingPartialAssistantTagRegex, "")
            .replace(clientToolMarkerRegex, "")
            .replace(awaitingMarkerRegex, "")
            .replace(trailingPartialAwaitingMarkerRegex, "")

    private fun removeTrailingPartialAwaitingMarker(text: String): String {
        val start = text.lastIndexOf("[[")
        if (start < 0) return text
        val tail = text.substring(start).uppercase()
        return if ("[[AWAITING:".startsWith(tail) || tail.startsWith("[[AWAITING:")) {
            text.substring(0, start)
        } else {
            text
        }
    }

    private fun normalizeTtsText(raw: String?): String =
        (raw ?: "").trim().replace(ttsCollapseWhitespaceRegex, " ").trim()
}
