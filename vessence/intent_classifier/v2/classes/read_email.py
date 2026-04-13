"""READ_EMAIL — read/check/search email inbox."""

CLASS_NAME = "READ_EMAIL"
NEEDS_LLM = True

EXAMPLES = [
    "check my email", "read my email", "any new emails",
    "do I have any emails", "what's in my inbox",
    "check my inbox", "any unread emails",
    "read emails from john", "any email from my boss",
    "check email from amazon", "did amazon email me",
    "what emails came in today", "any important emails",
    "read the latest email", "check for new mail",
    "any emails from work", "show my emails",
    "what's in my gmail", "check gmail",
    "any emails from sarah", "did the bank email me",
    "check if I have any emails from the doctor",
    "read unread emails", "any new mail",
    "show me my inbox", "pull up my email",
    "check work email", "any emails I missed",
    "did anyone email me", "what emails do I have",
    "check if I got a reply from john", "any responses to my email",
    "show emails from last hour", "any emails from the school",
    "read email from mom", "check for emails",
    "any news emails", "did the irs email me",
    "check my email for the confirmation", "any shipping emails",
    "show emails from amazon", "did uber eats email me",
    "any newsletters today", "check my spam",
    "any new messages in my inbox", "read the email from sarah",
    "check for recent emails", "any emails this morning",
]

CONTEXT = """\
The user wants to read or check their email inbox.
Output exactly:
CLASSIFICATION: READ_EMAIL
QUERY: <sender or search filter if mentioned, else "unread">"""
