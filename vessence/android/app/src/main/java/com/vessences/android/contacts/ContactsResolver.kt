package com.vessences.android.contacts

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.ContactsContract
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * On-device resolver for contacts. All queries happen on Dispatchers.IO.
 *
 * This is the ONE place that touches ContactsContract — both ContactsCallHandler
 * and ContactsSmsHandler go through here, so there's no duplicated query logic.
 *
 * The server never sees contact data: names, numbers, and contact IDs all
 * stay on the device.
 */
object ContactsResolver {

    /** A callable phone contact with one specific phone number. */
    data class Contact(
        val contactId: Long,
        val displayName: String,
        val phoneNumber: String,
        val isPrimary: Boolean,
    )

    /** Result of an exact-match resolution attempt. */
    sealed class ResolveResult {
        /** Exactly one callable contact with exactly one phone number. */
        data class Single(val contact: Contact) : ResolveResult()

        /** Multiple candidates — caller must disambiguate (ask user). */
        data class Multiple(val candidates: List<Contact>) : ResolveResult()

        /** Permission not granted. */
        object PermissionDenied : ResolveResult()

        /** No contact matched the query. */
        object None : ResolveResult()
    }

    /**
     * Search for callable contacts matching [query] using Android's
     * [ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI] for
     * smart matching, then rank results locally via a three-tier system:
     *
     *   Tier 1 — Exact full-name match (case-insensitive)
     *   Tier 2 — Name starts with query (first-name match)
     *   Tier 3 — Query matches a name TOKEN exactly (split on whitespace/parens)
     *
     * Lower-tier matches (substring inside parenthetical notes like
     * "Christine (friends contact)") are DISCARDED if any higher-tier match
     * exists. This prevents false positives from contact annotation text.
     *
     * Returns one [Contact] entry per distinct phone number — a person with
     * three numbers yields three entries.
     */
    suspend fun findCallable(ctx: Context, query: String): List<Contact> {
        if (!hasReadContactsPermission(ctx)) return emptyList()
        val trimmed = query.trim()
        if (trimmed.isEmpty()) return emptyList()
        val queryLower = trimmed.lowercase()

        return withContext(Dispatchers.IO) {
            val raw = mutableListOf<Contact>()

            // CONTENT_FILTER_URI does smart matching (respects locale, matches
            // nicknames, phonetic names) — better than raw LIKE %query%.
            val filterUri = android.net.Uri.withAppendedPath(
                ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI,
                android.net.Uri.encode(trimmed),
            )
            val projection = arrayOf(
                ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER,
                ContactsContract.CommonDataKinds.Phone.IS_PRIMARY,
            )

            try {
                ctx.contentResolver.query(filterUri, projection, null, null, null)
                    ?.use { cursor ->
                        val idIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
                        val nameIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                        val numIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER)
                        val primIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.IS_PRIMARY)
                        while (cursor.moveToNext()) {
                            val id = cursor.getLong(idIdx)
                            val name = cursor.getString(nameIdx) ?: continue
                            val number = cursor.getString(numIdx)?.trim() ?: continue
                            if (number.isEmpty()) continue
                            val primary = cursor.getInt(primIdx) > 0
                            raw.add(Contact(id, name, number, primary))
                        }
                    }
            } catch (e: Exception) {
                Log.w(TAG, "findCallable query failed", e)
            }

            // Local tiered ranking — discard low-quality matches when
            // higher-quality ones exist.
            val tier1 = mutableListOf<Contact>()  // exact full-name match
            val tier2 = mutableListOf<Contact>()  // starts-with
            val tier3 = mutableListOf<Contact>()  // token match
            val tier4 = mutableListOf<Contact>()  // everything else (substring in parens, etc)

            for (c in raw) {
                val nameLower = c.displayName.lowercase()
                val nameTokens = nameLower.split(Regex("[\\s().,;:/-]+")).filter { it.isNotBlank() }

                when {
                    nameLower == queryLower -> tier1.add(c)
                    nameLower.startsWith("$queryLower ") || nameLower.startsWith(queryLower) && nameLower.length == queryLower.length -> tier1.add(c)
                    nameTokens.any { it == queryLower } -> tier2.add(c)
                    nameTokens.any { it.startsWith(queryLower) } -> tier3.add(c)
                    else -> tier4.add(c)
                }
            }

            // Return the highest non-empty tier. Never mix tiers — that
            // prevents "Christine (friends contact)" from appearing alongside
            // the actual target contact if both matched.
            val best = when {
                tier1.isNotEmpty() -> tier1
                tier2.isNotEmpty() -> tier2
                tier3.isNotEmpty() -> tier3
                tier4.isNotEmpty() -> tier4
                else -> emptyList()
            }

            Log.i(TAG, "findCallable('$trimmed'): ${raw.size} raw → tier1=${tier1.size} tier2=${tier2.size} tier3=${tier3.size} tier4=${tier4.size} → returning ${best.size}")
            best
        }
    }

    /**
     * Resolve [query] to a single callable contact if possible.
     *
     * Policy:
     *  - No permission → [ResolveResult.PermissionDenied].
     *  - No match → [ResolveResult.None].
     *  - Exactly one Contact row (one person, one number) → [ResolveResult.Single].
     *  - Multiple rows where ALL rows share the same contactId → that is one
     *    person with multiple phone numbers; we pick the primary if exactly one
     *    is primary, otherwise return Multiple(candidates=all their numbers).
     *  - Multiple rows with different contactIds → always [ResolveResult.Multiple].
     *
     * Caller should speak the candidates and either ask the user to be more
     * specific (via TOOL_RESULT feedback channel) or show a picker.
     */
    suspend fun resolveExact(ctx: Context, query: String): ResolveResult {
        if (!hasReadContactsPermission(ctx)) return ResolveResult.PermissionDenied
        val all = findCallable(ctx, query)
        if (all.isEmpty()) return ResolveResult.None
        if (all.size == 1) return ResolveResult.Single(all[0])

        // Multiple rows — check if they all belong to the same contactId (one person, many numbers).
        val distinctPeople = all.map { it.contactId }.toSet()
        if (distinctPeople.size == 1) {
            // Same person, multiple numbers — try to pick primary.
            val primaries = all.filter { it.isPrimary }
            if (primaries.size == 1) return ResolveResult.Single(primaries[0])
            // No single primary — user must disambiguate between numbers.
            return ResolveResult.Multiple(all)
        }

        // Multiple distinct people — user must disambiguate.
        return ResolveResult.Multiple(all)
    }

    private fun hasReadContactsPermission(ctx: Context): Boolean =
        ContextCompat.checkSelfPermission(
            ctx,
            Manifest.permission.READ_CONTACTS,
        ) == PackageManager.PERMISSION_GRANTED

    private const val TAG = "ContactsResolver"
}
