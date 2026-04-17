"""todo_list class — read-only access to Chieh's personal TODO list.

The Google Doc is fetched periodically by
`agent_skills/fetch_todo_list.py` and cached as JSON. This handler reads
the cache on each user query — no edit/write path, this is a read-only
read-back of the mirrored doc.

Conversational flow:

  User: "what's on my todo list"
  Jane: "You've got 5 categories: Do it Immediately, For my students,
         For our Home, For the clinic, and Ambient project goals.
         Which one do you want to hear?"
         [pending_action: STAGE2_FOLLOWUP awaiting=category]

  User: "clinic"
  Jane: [handler gets routed directly back via resolver, reads cache,
         speaks the 2 clinic items]
"""
