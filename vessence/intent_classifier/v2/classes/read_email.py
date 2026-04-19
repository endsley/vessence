"""READ_EMAIL — read/check/search email inbox."""

CLASS_NAME = "READ_EMAIL"
NEEDS_LLM = True

EXAMPLES = [
    "check my email", "read my email", "any new emails",
    "do I have any emails", "what's in my inbox",
    "check my inbox", "any unread emails",
    "read emails from x", "any email from x",
    "check email from x", "did x email me",
    "what emails came in today", "any important emails",
    "read the latest email", "check for new mail",
    "any emails from work", "show my emails",
    "what's in my gmail", "check gmail",
    "any emails from x", "did the bank email me",
    "check if I have any emails from the doctor",
    "read unread emails", "any new mail",
    "show me my inbox", "pull up my email",
    "check work email", "any emails I missed",
    "did anyone email me", "what emails do I have",
    "check if I got a reply from x", "any responses to my email",
    "show emails from last hour", "any emails from the school",
    "read email from x", "check for emails",
    "any news emails", "did the irs email me",
    "check my email for the confirmation", "any shipping emails",
    "show emails from x", "did uber eats email me",
    "any newsletters today", "check my spam",
    "any new messages in my inbox", "read the email from x",
    "check for recent emails", "any emails this morning",
]

CONTEXT = """\
The user wants to read or check their email inbox.
Output exactly:
CLASSIFICATION: READ_EMAIL
QUERY: <sender or search filter if mentioned, else "unread">"""
