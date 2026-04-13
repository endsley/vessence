"""SEND_MESSAGE — text/SMS a person."""

CLASS_NAME = "SEND_MESSAGE"
NEEDS_LLM = True

EXAMPLES = [
    "text my wife I'll be home late", "tell kathia I miss her",
    "message john about the meeting", "let mom know I'm on my way",
    "send sarah a text saying I'm running late",
    "text my boss that I'll be in by 10",
    "tell my dad happy birthday",
    "message bob that the package arrived",
    "let my wife know dinner is ready",
    "send a text to john saying yes",
    "text mom that I love her",
    "tell my sister I'll call her later",
    "message my wife that I'm stuck in traffic",
    "let john know I can't make it",
    "text my friend that the plan is confirmed",
    "tell sarah I got her message",
    "message my dad that I'm okay",
    "let kathia know I'm thinking of her",
    "text my wife that I love her",
    "send bob a message saying good morning",
    "tell my coworker the meeting is cancelled",
    "message my wife I'll pick up the kids",
    "let my mom know I landed safely",
    "text john that I'm outside",
    "tell my boss I'm working from home today",
    "message sarah happy anniversary",
    "let my wife know I'm at the store",
    "text my dad that the game starts at 7",
    "send a message to kathia saying I'm free tonight",
    "tell john I'll be there in 5 minutes",
    "message my sister that I miss her",
    "let bob know the report is done",
    "text my wife good morning",
    "send mom a message saying I'm coming for dinner",
    "tell my friend I'm almost there",
    "message sarah that I got the job",
    "let my wife know to pick up milk",
    "text john that I found the place",
    "tell my boss I submitted the report",
    "message my wife to call me when she's free",
    "let sarah know the kids are asleep",
    "text bob that we're all set",
    "tell my mom I'll be home for Christmas",
    "message kathia I can't stop thinking about her",
    "let john know I'm done for the day",
    "text my wife I love her so much",
    "send a text to my dad saying call me",
    "tell my friend that I'm proud of them",
    "message my wife that I left work early",
    "let sarah know I'll be late to dinner",
    # Direct send-to patterns without inline body
    "send a text to my wife", "send a text to john", "send a text to bob",
    "text my wife", "text john for me", "shoot a text to bob",
    "send a message to my wife", "send a message to sarah",
    "can you send a text to my wife", "can you text my mom",
    # Continuation / confirmation to send
    "sounds good send it", "yeah send it", "go ahead and send it",
    "send it now", "ok send that", "please send that message",
    "yes send it", "send the message", "go ahead and text them",
    # Natural phrasing with "tell" and "can you"
    "can you tell my wife that I love her",
    "can you text my wife and tell her that I miss her today",
    "can you tell my wife I'm on my way",
    "tell my wife that I love her",
    "tell my wife I miss her",
    "can you tell my mom I said hi",
    "tell my dad I'll be late",
    # "text [name] [message]" patterns — critical to beat READ_MESSAGES
    "text romeo hey sorry for using you as my test subject",
    "text romeo I'll be there in 10 minutes",
    "text john hey what's up",
    "text sarah thanks for dinner last night",
    "text mom happy mothers day",
    "text dad I passed the exam",
    "text kathia I'm leaving work now",
    "text bob can you pick up the groceries",
    "text my friend hey are you free tonight",
    "text my brother happy birthday bro",
    "text romeo are you coming to the game tonight",
    "text john I just saw your message",
    "text sarah the reservation is at 7",
    # Short names — critical for first-name-only contacts
    "text li hey are you free today",
    "text li I'll see you at the courts",
    "send a message to li",
    "tell li I'm running late",
    "text bob hey",
    "text joe are you coming",
    "text sam thanks",
    "send li a text saying I'm on my way",
]

CONTEXT = """\
The user wants to TEXT/SMS someone. Never call — SMS only.
Output exactly:
CLASSIFICATION: SEND_MESSAGE
RECIPIENT: <name as said — keep "wife", "mom", "Kathia" literal>
BODY: <message text only>
COHERENT: yes | no   (no = garbled/cut-off/random words)"""
