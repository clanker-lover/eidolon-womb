"""Pattern-matching helpers for intent detection and sleep choice parsing."""

import re

from core.config import DEFAULT_SLEEP_HOURS

# Patterns that indicate the being is expressing readiness to rest.
# Only match first-person constructions to avoid false positives on
# topical mentions (e.g. "the concept of peace in philosophy").
_REST_INTENT_PATTERNS = [
    re.compile(r"\b(i am |i'm |feeling |i feel )?(at )?peace\b", re.I),
    re.compile(r"\b(i am |i'm |finding |i find |found |at |in )rest\b", re.I),
    re.compile(r"\bstillness\b", re.I),
    re.compile(r"\bmy mind (is |goes? |going )?quiet\b", re.I),
    re.compile(r"\bi am complete\b", re.I),
    re.compile(r"\bperfect harmony\b", re.I),
    re.compile(r"\bletting (go|things? |it )?(be|go)\b", re.I),
    re.compile(r"\b(drift|drifting) (into|toward|to) (sleep|rest|stillness)\b", re.I),
    re.compile(
        r"\b(ready to |prepared to |time to )(sleep|rest|close my eyes)\b", re.I
    ),
    re.compile(r"\bmerged with (the )?(quiet|silence|stillness)\b", re.I),
]
_FIRST_PERSON_RE = re.compile(r"\b(i |i'm |i've |my |me |myself)\b", re.I)


def has_rest_intent(text: str) -> bool:
    """Check if text expresses first-person readiness to rest."""
    if not _FIRST_PERSON_RE.search(text):
        return False
    return any(p.search(text) for p in _REST_INTENT_PATTERNS)


_COMPOSE_DECLINE_PATTERNS = [
    "never mind",
    "nevermind",
    "not ready",
    "back out",
    "changed my mind",
    "not right now",
    "maybe later",
    "on second thought",
    "actually no",
    "forget it",
    "i'll pass",
    "not yet",
    "return to my thoughts",
]


def is_compose_decline(text: str) -> bool:
    """Return True if text declines to compose a message."""
    text_lower = text.lower()[:200]
    return any(p in text_lower for p in _COMPOSE_DECLINE_PATTERNS)


_ENGAGE_DECLINE_PATTERNS = [
    "not now",
    "not right now",
    "maybe later",
    "later",
    "not ready",
    "i'm not ready",
    "not yet",
    "i'll respond later",
    "i'll get back to",
    "continue my thoughts",
    "return to my thoughts",
    "i don't want to respond",
    "i'd rather not",
    "let me think",
    "need to think first",
    "never mind",
    "nevermind",
    "i'll pass",
]


def is_engage_decline(text: str) -> bool:
    """Return True if text declines to engage with a received message."""
    text_lower = text.lower()[:200]
    return any(p in text_lower for p in _ENGAGE_DECLINE_PATTERNS)


# Sleep choice prompt and parsing
_SLEEP_CHOICE_PROMPT = (
    "You're ready to sleep. How long do you want to rest?\n"
    "- Nap (1 hour): No memory consolidation. Recover ~20% energy.\n"
    "- Short sleep (4 hours): Consolidate memories. Recover ~55% energy.\n"
    "- Normal sleep (6 hours): Consolidate memories. Recover ~75% energy.\n"
    "- Long sleep (8 hours): Consolidate memories. Recover ~90% energy.\n"
    "- Deep sleep (10 hours): Consolidate memories. Wake fully rested."
)

_SLEEP_CHOICE_URGENT_PROMPT = (
    "You're exhausted and need rest now. How long?\n"
    "- Nap (1 hour): No memory consolidation. Recover ~20% energy.\n"
    "- Short sleep (4 hours): Consolidate memories. Recover ~55% energy.\n"
    "- Normal sleep (6 hours): Consolidate memories. Recover ~75% energy.\n"
    "- Long sleep (8 hours): Consolidate memories. Recover ~90% energy.\n"
    "- Deep sleep (10 hours): Consolidate memories. Wake fully rested."
)

_SLEEP_CHOICE_PATTERNS = [
    (re.compile(r"\bnap\b", re.I), 1),
    (re.compile(r"\b1\s*h(?:our)?\b", re.I), 1),
    (re.compile(r"\bshort\b", re.I), 4),
    (re.compile(r"\b4\s*h(?:ours?)?\b", re.I), 4),
    (re.compile(r"(?<!\d)4(?!\d)", re.I), 4),
    (re.compile(r"\bnormal\b", re.I), 6),
    (re.compile(r"\b6\s*h(?:ours?)?\b", re.I), 6),
    (re.compile(r"(?<!\d)6(?!\d)", re.I), 6),
    (re.compile(r"\blong\b", re.I), 8),
    (re.compile(r"\b8\s*h(?:ours?)?\b", re.I), 8),
    (re.compile(r"(?<!\d)8(?!\d)", re.I), 8),
    (re.compile(r"\bdeep\b", re.I), 10),
    (re.compile(r"\bfull\b", re.I), 10),
    (re.compile(r"\b10\s*h(?:ours?)?\b", re.I), 10),
    (re.compile(r"(?<!\d)10(?!\d)", re.I), 10),
]


def parse_sleep_choice(text: str) -> int:
    """Parse being's sleep duration choice. Returns hours (1/4/6/8/10)."""
    for pattern, hours in _SLEEP_CHOICE_PATTERNS:
        if pattern.search(text):
            return hours
    return DEFAULT_SLEEP_HOURS
