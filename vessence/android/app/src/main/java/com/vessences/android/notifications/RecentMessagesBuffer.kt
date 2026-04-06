package com.vessences.android.notifications

import java.util.concurrent.ConcurrentLinkedDeque

/**
 * Bounded in-memory ring buffer of recent messaging-category notifications.
 *
 * Fed by [VessenceNotificationListener] and read by [com.vessences.android.tools.MessagesReadRecentHandler].
 *
 * Invariants:
 *  - At most [CAPACITY] entries.
 *  - Newest at the head, oldest at the tail.
 *  - In-memory only — cleared on process kill.
 *  - NEVER uploaded to the server; never touches disk.
 */
object RecentMessagesBuffer {

    /**
     * @property sender Display name from MessagingStyle.Person or the
     *   notification's android.title extra (best effort).
     * @property body Message text as read from MessagingStyle.Message or
     *   the notification's android.text extra.
     * @property timestamp When the message arrived (epoch ms).
     * @property packageName Originating app package — used by the read handler
     *   to allow/deny lists if Chieh wants to filter per-app later.
     * @property sbnKey Unique notification key, used for deduping updates to
     *   the same notification (many apps update in-place when a reply arrives).
     */
    data class Entry(
        val sender: String,
        val body: String,
        val timestamp: Long,
        val packageName: String,
        val sbnKey: String,
    )

    private const val CAPACITY = 20

    private val deque: ConcurrentLinkedDeque<Entry> = ConcurrentLinkedDeque()

    /**
     * Shared lock for compound mutations (remove-then-add-then-trim).
     * `ConcurrentLinkedDeque`'s individual methods are thread-safe, but
     * the "remove duplicate sbnKey, then addFirst, then trim to CAPACITY"
     * sequence is NOT atomic and can duplicate or over/undershoot capacity
     * under rapid concurrent [record] calls. All mutating entry points
     * synchronize on this lock.
     */
    private val lock = Any()

    /**
     * Record a new message. If an entry with the same [Entry.sbnKey] already
     * exists (common for apps that update the notification in place), the old
     * entry is removed and the new one is added at the head. The entire
     * operation is atomic under [lock] so concurrent posts cannot duplicate
     * entries or exceed [CAPACITY].
     */
    fun record(entry: Entry) {
        synchronized(lock) {
            // Remove any prior entry with the same sbnKey (in-place updates).
            val it = deque.iterator()
            while (it.hasNext()) {
                if (it.next().sbnKey == entry.sbnKey) it.remove()
            }
            deque.addFirst(entry)
            while (deque.size > CAPACITY) {
                deque.pollLast()
            }
        }
    }

    /** Return up to [limit] most recent entries, newest first. */
    fun snapshot(limit: Int): List<Entry> =
        synchronized(lock) { deque.toList().take(limit.coerceAtLeast(0)) }

    /** Total number of buffered entries. */
    fun size(): Int = deque.size

    /** Purge everything — used when the listener disconnects. */
    fun clear() {
        synchronized(lock) { deque.clear() }
    }
}
