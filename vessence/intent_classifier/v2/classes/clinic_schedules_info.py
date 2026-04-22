"""CLINIC_SCHEDULES_INFO — read a practitioner's current-week booked appointment list.

Chroma exemplars here MUST contain a clinic-specific noun — "patient(s)",
"clinic", or a "clinic schedule"-style phrase. Generic wording like
"how busy is she on Monday" or "who's coming in today" is deliberately
excluded: those phrases could plausibly belong to other classes (personal
calendar, general scheduling) and would pollute chroma. See the
`class_exemplar_specificity` entry in preference_registry.json.

Short topical follow-ups like "what about Tuesday" or "how about next
Monday" are NOT in chroma either — the clinic handler attaches a
STAGE2_FOLLOWUP pending_action with a literal question, and the
dispatcher's continuation gate routes those short replies back to the
handler directly. Embedding bare weekdays here would hijack unrelated
conversations that mention a day.
"""

CLASS_NAME = "CLINIC_SCHEDULES_INFO"
NEEDS_LLM = False

EXAMPLES = [
    # ── per-weekday patient counts ───────────────────────────────────────
    "how many patients does she have on Monday",
    "how many patients does she have on Tuesday",
    "how many patients does she have on Wednesday",
    "how many patients does she have on Thursday",
    "how many patients does she have on Friday",
    "who are the patients for her on Monday",
    "who are the patients for her on Tuesday",
    "who are the patients for her on Wednesday",
    "who are the patients for her on Thursday",
    "who are the patients for her on Friday",

    # ── first-person / "today" patient variants ──────────────────────────
    "how many patients do I have today",
    "how many patients do I have tomorrow",
    "how many patients today",
    "how many patients tomorrow",
    "any patients today",
    "any patients tomorrow",
    "my patients today",
    "my patients tomorrow",
    "which patients are coming in *",
    "patients today",
    "patients tomorrow",
    "patients this week",

    # ── clinic schedule phrasing ─────────────────────────────────────────
    "can you tell me about the clinic schedule on Monday",
    "can you tell me about the clinic schedule on Wednesday",
    "what does the clinic schedule look like on Friday",
    "what is the clinic schedule for Thursday",
    "give me the clinic schedule for Tuesday",
    "what does my clinic schedule look like tomorrow",
    "what is my clinic schedule look like tomorrow",
    "what does my clinic schedule look like on Wednesday",
    "how does my clinic schedule look on Monday",
    "my clinic schedule",
    "what's my clinic schedule",
    "what's the clinic schedule",
    "what's the clinic look like today",
    "what does the clinic look like this week",

    # ── cancellation queries (clinic-patient only) ───────────────────────
    "which patients canceled",
    "which patients cancelled",
    "which patients canceled today",
    "did any patients cancel",
]
