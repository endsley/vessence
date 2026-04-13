"""GREETING — standalone greetings with no task attached."""

CLASS_NAME = "GREETING"
NEEDS_LLM = False  # No metadata to extract; delegates to standing brain for contextual response

EXAMPLES = [
    # Basic greetings
    "hey", "hi", "hello", "hey jane", "hi jane", "hello jane",
    "good morning", "good morning jane", "morning", "morning jane",
    "good afternoon", "good evening", "evening",
    # Casual / slang
    "what's up", "what's up jane", "sup", "yo", "yo jane",
    "howdy", "hiya", "heya", "hey there", "hi there",
    "greetings", "salut", "hola", "ciao",
    # With punctuation / energy
    "hey, you there?", "hi!", "hello!", "hey!", "good morning!",
    "hey, wake up", "good evening jane", "hey jane, you there?",
    "hi there jane", "hello there", "hey hey",
    "what's good", "what's good jane", "yo yo", "hola jane",
    "hey jane!", "hi jane!", "morning!", "evening!",
    "hey, hi", "sup jane", "howdy jane",
    "greetings jane",
    # Presence checks
    "are you there", "is anyone there", "hello are you there",
    "hey are you there", "jane are you there", "you there",
    "hello is anyone listening", "hey are you awake", "you awake",
    # Check-ins / how are you
    "how's it going", "how's it going jane", "how are you", "how are you doing",
    "how are you jane", "how you doing", "how's everything", "how's everything going",
    "how have you been", "how's your day", "how's your day going",
    "how's life", "what's new", "what's new with you", "what's going on",
    "what's going on jane", "you doing okay", "you good", "you good jane",
    "everything okay", "all good", "you alright", "you alright jane",
    # Longer casual openers
    "hey jane how are you", "hi jane how's it going", "hello how are you",
    "hey, how have you been", "good to see you", "nice to see you",
    "long time no talk", "hey stranger", "oh hey", "oh hi",
    "well hello there", "well hi there", "hey you", "hi you",
    # Time-specific
    "afternoon", "good day", "good day jane", "top of the morning",
    "rise and shine", "wakey wakey",
    # Ambiguous catch-ups — must NOT trigger data fetches
    "anything new", "anything going on", "any updates", "what's happening",
    "is there anything", "catch me up", "fill me in", "what's the latest",
    "anything i missed", "what did i miss", "what's up with you",
    # Minimal pings / name calls
    "jane", "jane?", "hey jane?", "you there jane",
    "test", "testing", "hey, test", "testing testing",
]

CONTEXT = None  # No LLM call for Stage 2 — delegates to standing brain
