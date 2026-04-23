"""READ_CALENDAR — read/check Google Calendar events.

Intentionally narrow: only phrasings that unambiguously ASK to see what's
already on the calendar. Create / edit / cancel events and "tell X about
my meeting" are NOT this class — they belong to DELEGATE_OPUS / SEND_MESSAGE.
"""

CLASS_NAME = "READ_CALENDAR"
NEEDS_LLM = True

EXAMPLES = [
    # "calendar" noun — strongest and safest read signal
    "what's on my calendar today",
    "what's on my calendar tomorrow",
    "what's on my calendar this week",
    "what's on my calendar this weekend",
    "what's on my calendar",
    "check my calendar",
    "check my calendar today",
    "check my calendar tomorrow",
    "read my calendar",
    "read my calendar today",
    "show me my calendar",
    "show me my calendar today",
    "pull up my calendar",
    "pull up my calendar today",
    "open my calendar",
    "look at my calendar",
    "anything on my calendar today",
    "anything on my calendar tomorrow",
    "anything on my calendar this week",
    "what do I have on my calendar today",
    "what do I have on my calendar tomorrow",
    "what's scheduled on my calendar",
    # "agenda" noun — unique and safe
    "what's on my agenda today",
    "what's on my agenda tomorrow",
    "what's on my agenda this week",
    "show me my agenda today",
    "read my agenda today",
    "check my agenda",
    # "schedule" noun — personal schedule means Google Calendar. Bare
    # "the schedule" stays available for clinic schedule routing.
    "read my calendar schedule today",
    "show me my calendar schedule today",
    "what's my schedule today",
    "what's my schedule tomorrow",
    "what's my schedule for Thursday",
    "what does my schedule look like Thursday",
    "show me my schedule for Thursday",
    # Explicit "events on my calendar" phrasings
    "what events are on my calendar today",
    "what events are on my calendar tomorrow",
    "list the events on my calendar today",
    # "next event" / upcoming phrasings
    "what's my next event",
    "when is my next event",
    "tell me my next event",
    "what's coming up on my calendar",
    "do I have anything coming up",
    "what's next on my calendar",
    "when's my next appointment",
    "what's my next meeting",
]

CONTEXT = """\
The user wants to read or check events on their Google Calendar.
ONLY for reading — NOT for creating, editing, moving, or cancelling events.
NOT for texting someone about a meeting (that's SEND_MESSAGE).
Output exactly:
CLASSIFICATION: READ_CALENDAR
RANGE: <today|tomorrow|this_week|next_week|weekend|next|YYYY-MM-DD, default "today">"""
