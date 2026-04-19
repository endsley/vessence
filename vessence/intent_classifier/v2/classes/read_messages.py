"""READ_MESSAGES — read/check incoming text messages."""

CLASS_NAME = "READ_MESSAGES"
NEEDS_LLM = True

EXAMPLES = [
    # All examples explicitly mention texts/messages/SMS
    "read my texts", "check my messages", "read my messages",
    "any new texts", "any new text messages", "do I have any texts",
    "what did x text me", "did x text me",
    "read texts from x", "any messages from x",
    "check texts from x", "what did x say in his text",
    "read my unread messages", "show my texts",
    "what texts do I have", "any new texts from anyone",
    "read the message from x", "what did she text",
    "check if anyone texted me", "any texts while I was driving",
    "read my text messages", "pull up my texts",
    "what text messages came in", "any texts from x",
    "show messages from x", "check my SMS",
    "read SMS from x", "any unread texts",
    "read the last text message",
    "check texts from work", "any text messages from x",
    "pull up texts from last hour", "read new text messages",
    "what's in my text inbox", "do I have unread texts",
    "show my unread text messages", "read that last text",
    "check messages from x",
    "read all my text messages", "did x message me",
    "show new texts", "did anyone text me",
    "what text messages do I have", "check text messages",
    "read recent texts", "show me my texts",
    "any new texts from x", "check if x texted me",
    # Additional patterns from real usage
    "can you read me the most recent message", "read me the most recent text",
    "read me the last message", "read me the last text",
    "how many messages did I get yesterday", "how many texts came in today",
    "how many messages from yesterday", "how many texts did I receive today",
    "check if I have any new texts", "any new texts for me",
    "did I get any new texts", "any new messages for me",
    "what messages came in", "what texts came in today",
    "any messages since this morning", "any texts in the last hour",
    # Additional real-usage patterns
    "how many messages do I have today from text",
    "how many text messages do I have today",
    "can you look at read the last three text messages",
    "look at my last three text messages",
    "you look at my text messages for me",
    "look at my text messages", "check my text messages for me",
    "read the most recent text message",
    "what's the latest text", "any messages from today",
    "how many texts from today", "how many unread messages do I have",
]

CONTEXT = """\
The user wants to read/check their text messages.
Output exactly:
CLASSIFICATION: READ_MESSAGES
FILTER: <sender name if mentioned, else "all">"""
