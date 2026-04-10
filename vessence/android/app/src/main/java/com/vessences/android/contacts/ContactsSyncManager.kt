package com.vessences.android.contacts

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.ContactsContract
import android.util.Log
import androidx.core.content.ContextCompat
import com.vessences.android.data.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Syncs the device's contacts (names, phone numbers, emails) to the Vessence server
 * so Jane can look up contact info when composing emails or messages.
 *
 * Sync is a full replace — every sync sends all contacts. The server upserts
 * based on the UNIQUE(display_name, phone_number, email) constraint.
 */
object ContactsSyncManager {

    private const val TAG = "ContactsSyncManager"
    private const val PREFS_NAME = "contacts_sync"
    private const val KEY_LAST_SYNC = "last_sync_ms"
    private const val SYNC_INTERVAL_MS = 6 * 60 * 60 * 1000L  // 6 hours

    /**
     * Sync contacts if enough time has elapsed since the last sync.
     * Call this from MainActivity.onCreate after permissions are granted.
     */
    suspend fun syncIfNeeded(context: Context) {
        if (!hasPermission(context)) {
            Log.d(TAG, "READ_CONTACTS permission not granted, skipping sync")
            return
        }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val lastSync = prefs.getLong(KEY_LAST_SYNC, 0L)
        val now = System.currentTimeMillis()
        if (now - lastSync < SYNC_INTERVAL_MS) {
            Log.d(TAG, "Last sync was ${(now - lastSync) / 1000}s ago, skipping")
            return
        }
        try {
            val contacts = queryAllContacts(context)
            if (contacts.isEmpty()) {
                Log.d(TAG, "No contacts found on device")
                return
            }
            uploadContacts(contacts)
            prefs.edit().putLong(KEY_LAST_SYNC, now).apply()
            Log.i(TAG, "Synced ${contacts.size} contacts to server")
        } catch (e: Exception) {
            Log.e(TAG, "Contact sync failed", e)
        }
    }

    /**
     * Force a sync regardless of the interval timer.
     */
    suspend fun forceSync(context: Context) {
        if (!hasPermission(context)) return
        try {
            val contacts = queryAllContacts(context)
            uploadContacts(contacts)
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().putLong(KEY_LAST_SYNC, System.currentTimeMillis()).apply()
            Log.i(TAG, "Force-synced ${contacts.size} contacts")
        } catch (e: Exception) {
            Log.e(TAG, "Force sync failed", e)
        }
    }

    /**
     * Query all contacts with phone numbers and/or emails from the device.
     * Returns a flat list — one entry per (name, phone) and one per (name, email).
     */
    private suspend fun queryAllContacts(context: Context): List<Map<String, Any?>> =
        withContext(Dispatchers.IO) {
            val contacts = mutableListOf<Map<String, Any?>>()
            val seenPhones = mutableSetOf<String>()  // dedupe key: "name|phone"
            val seenEmails = mutableSetOf<String>()   // dedupe key: "name|email"

            // Query phone numbers
            try {
                val phoneCursor = context.contentResolver.query(
                    ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                    arrayOf(
                        ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                        ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                        ContactsContract.CommonDataKinds.Phone.NUMBER,
                        ContactsContract.CommonDataKinds.Phone.IS_PRIMARY,
                    ),
                    null, null, null,
                )
                phoneCursor?.use { cursor ->
                    val idIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
                    val nameIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                    val numIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER)
                    val primIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.IS_PRIMARY)
                    while (cursor.moveToNext()) {
                        val name = cursor.getString(nameIdx) ?: continue
                        val number = cursor.getString(numIdx)?.trim() ?: continue
                        if (number.isEmpty()) continue
                        val key = "${name}|${number}"
                        if (key in seenPhones) continue
                        seenPhones.add(key)
                        contacts.add(mapOf(
                            "display_name" to name,
                            "phone_number" to number,
                            "email" to null,
                            "is_primary" to (cursor.getInt(primIdx) > 0),
                            "contact_id" to cursor.getString(idIdx),
                        ))
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Error querying phone contacts", e)
            }

            // Query email addresses
            try {
                val emailCursor = context.contentResolver.query(
                    ContactsContract.CommonDataKinds.Email.CONTENT_URI,
                    arrayOf(
                        ContactsContract.CommonDataKinds.Email.CONTACT_ID,
                        ContactsContract.CommonDataKinds.Email.DISPLAY_NAME,
                        ContactsContract.CommonDataKinds.Email.ADDRESS,
                        ContactsContract.CommonDataKinds.Email.IS_PRIMARY,
                    ),
                    null, null, null,
                )
                emailCursor?.use { cursor ->
                    val idIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Email.CONTACT_ID)
                    val nameIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Email.DISPLAY_NAME)
                    val emailIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Email.ADDRESS)
                    val primIdx = cursor.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Email.IS_PRIMARY)
                    while (cursor.moveToNext()) {
                        val name = cursor.getString(nameIdx) ?: continue
                        val email = cursor.getString(emailIdx)?.trim() ?: continue
                        if (email.isEmpty()) continue
                        val key = "${name}|${email}"
                        if (key in seenEmails) continue
                        seenEmails.add(key)
                        contacts.add(mapOf(
                            "display_name" to name,
                            "phone_number" to null,
                            "email" to email,
                            "is_primary" to (cursor.getInt(primIdx) > 0),
                            "contact_id" to cursor.getString(idIdx),
                        ))
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Error querying email contacts", e)
            }

            Log.d(TAG, "Queried ${contacts.size} contact entries (${seenPhones.size} phones, ${seenEmails.size} emails)")
            contacts
        }

    private suspend fun uploadContacts(contacts: List<Map<String, Any?>>) {
        withContext(Dispatchers.IO) {
            val response = ApiClient.janeApi.syncContacts(contacts)
            if (response.isSuccessful) {
                Log.i(TAG, "Upload success: ${response.body()}")
            } else {
                Log.e(TAG, "Upload failed: ${response.code()} ${response.errorBody()?.string()}")
            }
        }
    }

    private fun hasPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) ==
            PackageManager.PERMISSION_GRANTED
}
