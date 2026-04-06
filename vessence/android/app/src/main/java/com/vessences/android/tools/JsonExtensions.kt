package com.vessences.android.tools

import com.google.gson.JsonElement
import com.google.gson.JsonObject

/**
 * Shared Gson defensive accessors used by every ClientToolHandler.
 *
 * Before this existed, `asSafeString` and `asSafeInt` were re-implemented in
 * five different files (ClientToolDispatcher, ContactsCallHandler,
 * ContactsSmsHandler, MessagesReadRecentHandler, MessagesFetchUnreadHandler)
 * with subtle variations. Consolidating prevents drift and guarantees every
 * handler sees identical edge-case behavior.
 */

/**
 * Safe extraction of a JSON string value. Returns null if the element is
 * missing, JSON-null, or any non-primitive / non-string type.
 *
 * Accepts numeric primitives as strings too — this covers the case where
 * a server sends `draft_id: 42` instead of `draft_id: "42"`, which the
 * original strict `isString` check rejected and caused "missing draft_id"
 * failures even though the ID was present.
 */
internal fun JsonElement?.asSafeString(): String? {
    if (this == null || this.isJsonNull) return null
    if (!this.isJsonPrimitive) return null
    val p = this.asJsonPrimitive
    return when {
        p.isString -> p.asString
        p.isNumber -> p.asNumber.toString()
        p.isBoolean -> p.asBoolean.toString()
        else -> null
    }
}

/**
 * Safe extraction of a JSON integer value. Returns null if missing, JSON-null,
 * non-primitive, or not coercible to an int.
 */
internal fun JsonElement?.asSafeInt(): Int? {
    if (this == null || this.isJsonNull || !this.isJsonPrimitive) return null
    val p = this.asJsonPrimitive
    return try {
        when {
            p.isNumber -> p.asInt
            p.isString -> p.asString?.toIntOrNull()
            else -> null
        }
    } catch (e: Exception) {
        null
    }
}

/**
 * Require a non-empty string arg by key. Returns the trimmed string or null
 * if missing/blank. Use in preference to raw `asSafeString()` when empty
 * values are never valid (e.g., contact names, draft IDs).
 */
internal fun JsonObject.requireString(key: String): String? {
    val raw = this.get(key).asSafeString()?.trim() ?: return null
    return raw.ifBlank { null }
}
