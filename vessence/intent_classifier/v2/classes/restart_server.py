"""RESTART_SERVER — admin-style requests to restart Jane / the Jane server.

These are meta/admin commands that must reach Opus (the full LLM brain), not be
swallowed by fast-path intents like SYNC_MESSAGES, TIMER, or END_CONVERSATION.
The jane_proxy cascade has no explicit handler for this class, so it falls
through to the Claude/Opus brain — which is exactly what we want. The class
exists purely to win the vector vote and keep these phrases out of unrelated
fast paths.

Scope is deliberately narrow: only phrases that clearly name "jane" or
"the server/service/backend" as the restart target. Generic "restart my phone"
style requests fall to DELEGATE_OPUS via counter-examples there.
"""

CLASS_NAME = "RESTART_SERVER"
NEEDS_LLM = False

EXAMPLES = [
    # Restart / reboot — jane-targeted
    "restart jane",
    "restart the jane server",
    "restart jane web",
    "restart jane-web",
    "reboot jane",
    "reboot the jane server",
    "cycle jane",
    "bounce jane",
    "relaunch jane",
    "reload jane",
    # Restart / reboot — server-targeted (imperative commands only)
    "please restart the server",
    "go ahead and restart the server",
    "restart the server now",
    "reboot the server now",
    "please reboot the server",
    "bounce the server",
    "cycle the server",
    "kick the server",
    "respawn the server",
    # "hey opus / claude" admin prefixes (user explicitly routing to Opus)
    "hey opus please restart the server",
    "hey opus please restart the server i am ready",
    "hey opus restart the jane server",
    "opus please restart the server",
    "opus please restart jane",
    "claude please restart the server",
    "hey claude restart the jane server",
    # Graceful / zero-downtime restart phrasings
    "do a graceful restart of the server",
    "run a graceful restart of jane",
    "do a zero-downtime restart of the server",
    "restart jane gracefully",
    "graceful restart jane",
    # Shutdown / start — jane/server-targeted imperatives
    "shut down the jane server",
    "shutdown the jane server",
    "stop the jane server",
    "kill the jane server",
    "bring the jane server down",
    "bring jane down",
    "bring jane back up",
    "start the jane server",
    "start jane back up",
    # Indirect imperatives that still name jane/the server
    "can you restart the jane server",
    "could you restart the jane server",
    "i need you to restart the jane server",
    "time to restart the jane server",
    "let's restart the jane server",
    "please do a restart of jane",
    "do a restart of the jane server",
]

CONTEXT = None
