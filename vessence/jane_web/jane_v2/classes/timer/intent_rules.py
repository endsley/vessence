"""Legacy timer intent phrase rules."""

from __future__ import annotations


CANCEL_WORDS = (
    "cancel", "stop", "kill", "turn off", "clear", "never mind",
    "nevermind", "forget the timer", "abort",
)
LIST_WORDS = (
    "what timers", "list", "show my timer", "show me my timer",
    "any timers", "how much time", "how long", "time remaining",
    "time left", "what's on my timer", "do i have any timer",
    "check my timer",
)
COUNT_PHRASES = (
    "how many timers", "how many timer",
    "number of timers", "count my timers", "count of timers",
)
TIMER_NOUNS = ("timer", "countdown", "ticking")
STRICT_LIST_PHRASES = (
    "what timers", "any timers", "do i have any timer",
    "check my timer", "show my timer", "show me my timer",
)
CREATE_TIMER_WORDS = ("timer", "alarm", "countdown")
CREATE_VERBS = (
    "create", "make", "start", "begin", "set up", "set a",
    "set the", "set my", "start a", "make me a", "give me a",
    "need a", "need another",
)
SET_TRIGGERS = (
    "timer", "alarm", "countdown", "remind", "wake", "buzz",
    "nudge", "ping", "tell me when", "let me know", "set",
    "start", "give me", "gimme", "hit me", "time me",
)


def is_count_query(prompt_lower: str) -> bool:
    return any(phrase in prompt_lower for phrase in COUNT_PHRASES)


def is_cancel_query(prompt_lower: str) -> bool:
    return any(word in prompt_lower for word in CANCEL_WORDS) and "timer" in prompt_lower


def is_list_query(prompt_lower: str) -> bool:
    return (
        any(word in prompt_lower for word in LIST_WORDS)
        and (
            any(noun in prompt_lower for noun in TIMER_NOUNS)
            or any(phrase in prompt_lower for phrase in STRICT_LIST_PHRASES)
        )
    )


def wants_timer_creation(prompt_lower: str) -> bool:
    return (
        any(word in prompt_lower for word in CREATE_TIMER_WORDS)
        or any(verb in prompt_lower for verb in CREATE_VERBS)
    )


def has_timer_set_trigger(prompt: str, prompt_lower: str) -> bool:
    return len((prompt or "").split()) <= 4 or any(trigger in prompt_lower for trigger in SET_TRIGGERS)
