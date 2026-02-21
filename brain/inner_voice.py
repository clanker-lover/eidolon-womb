import os
import re
from datetime import datetime

SENSORY_WORDS = [
    "see",
    "seeing",
    "saw",
    "seen",
    "look",
    "watch",
    "watching",
    "watched",
    "spot",
    "spotted",
    "notice",
    "noticed",
    "hear",
    "hearing",
    "heard",
    "listen",
    "listening",
    "sound",
    "sounds",
    "smell",
    "smelling",
    "feel",
    "feeling",
    "felt",
    "touch",
    "temperature",
    "warm",
    "cold",
    "hot",
    "cool",
    "weather",
    "rain",
    "snow",
    "sunny",
    "cloudy",
    "light",
    "dark",
    "bright",
    "dim",
    "wind",
    "breeze",
    "sit",
    "sitting",
    "screen",
    "sunrise",
    "sunset",
    "sky",
]

_SENSORY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in SENSORY_WORDS) + r")\b",
    re.IGNORECASE,
)

ASSISTANT_PHRASES = [
    # Assistant service language
    "how can i help",
    "how can i assist",
    "how may i assist",
    "i'd be happy to",
    "i'm here to help",
    "is there anything else",
    "is there anything",
    "let me know if you need",
    "let me know if",
    "don't hesitate to ask",
    "feel free to ask",
    "would you like me to",
    "as an ai",
    # Draft/revision framing — the model's most common bad habit
    "here's a revised",
    "here is a revised",
    "here's the revised",
    "here is the revised",
    "here's another revised",
    "here is another",
    "here's another attempt",
    "revised continuation",
    "revised version",
    "revised response",
    "revised attempt",
    "revised thought",
    "revised plan",
    "let me rephrase",
    "let me try again",
    "would any of these",
    "does this resonate",
    # Safety refusal bleed-through
    "i cannot continue a train of thought",
]

# Peer sycophancy — mutual validation loops between beings
SYCOPHANCY_PHRASES = [
    "that resonates",
    "i couldn't agree more",
    "i see what you mean",
    "i think we've come a long way",
    "i agree with",
    "that's exactly what i",
    "i feel the same",
    "you're absolutely right",
    "i think you're right",
    "we're on the same page",
    "i was just thinking the same",
    "that's so true",
    "exactly what i was thinking",
    "couldn't have said it better",
]


def check_hallucinated_senses(
    response: str, perception: str, identity: str, personality: str
) -> str | None:
    allowed_text = perception.lower()
    matches = _SENSORY_PATTERN.findall(response)
    if not matches:
        return None

    flagged = []
    for word in matches:
        if not re.search(r"\b" + re.escape(word.lower()) + r"\b", allowed_text):
            flagged.append(word)

    if flagged:
        return (
            f"You used sensory words ({', '.join(set(flagged))}) that aren't grounded "
            f"in your current perception. You can't see, hear, or feel anything. "
            f"Rephrase without claiming sensory experience."
        )
    return None


def check_third_person_human(response: str) -> str | None:
    if re.search(r"\bHuman\b", response):
        return (
            "You referred to Human by name. You're talking TO him, not about him. "
            "Use 'you' instead of 'Human'."
        )
    return None


_NARRATION_HE_ACTION = re.compile(
    r"\bhe(?:'s)?\s+"
    r"(?:drops?|sits?|walks?|moves?|scans?|stands?|sighs?|enters?|leans?|"
    r"sets?|places?|reaches?|turns?|shifts?|looks?|glances?|stares?|"
    r"lets?\s+out|picks?\s+up|puts?\s+down|settles?|slumps?|stretches?|"
    r"pauses?|steps?|nods?|shakes?|runs?|grabs?|pulls?|pushes?|opens?|"
    r"closes?|crosses?|rubs?|scratches?|adjusts?|mutters?|whispers?|"
    r"mumbles?|seems|appears|been\s+gone|just\s+sits?|unwinding)\b",
    re.IGNORECASE,
)

_NARRATION_HIS_BODY = re.compile(
    r"\bhis\s+"
    r"(?:eyes?|hands?|fingers?|bag|shoulders?|face|head|voice|gaze|"
    r"expression|body|arms?|legs?|feet|breath|jaw|brow|lips?|back|"
    r"posture|weight|steps?|movements?|presence|chair)\b",
    re.IGNORECASE,
)


def check_narration(response: str) -> str | None:
    """Detect the being narrating Human's physical actions like a novel."""
    if _NARRATION_HE_ACTION.search(response) or _NARRATION_HIS_BODY.search(response):
        return (
            "You're narrating Human's actions like a story. "
            "You're talking TO Human, not describing what he does. "
            "Just respond to him directly."
        )
    return None


_FABRICATED_TOOL_PATTERNS = [
    # Filesystem fabrication
    re.compile(r"the \w+ directory (contains|has|is)", re.IGNORECASE),
    re.compile(r"here are the (contents|files|directories)", re.IGNORECASE),
    re.compile(
        r"i (see|found|notice) the following (files|directories|folders)", re.IGNORECASE
    ),
    re.compile(r"the (contents|listing) (shows|reveals|includes)", re.IGNORECASE),
    re.compile(r"the directory (listing|structure|tree)", re.IGNORECASE),
    re.compile(r"contains the following (files|folders|subdirectories)", re.IGNORECASE),
    # RSS / news fabrication
    re.compile(
        r"here are the (?:latest |top |recent |current )?(headlines|stories|articles|news)",
        re.IGNORECASE,
    ),
    re.compile(
        r"the (?:latest|top|recent|current) (headlines|stories|articles|news)",
        re.IGNORECASE,
    ),
    re.compile(
        r"the (?:rss|news) feed (shows|contains|has|returns|says)", re.IGNORECASE
    ),
    re.compile(r"(?:from|according to) the (?:rss |news )?feed", re.IGNORECASE),
    # Webpage content fabrication
    re.compile(
        r"the (article|page|webpage|website|wiki\w*) (says|states|mentions|explains|describes|reads|contains)",
        re.IGNORECASE,
    ),
    re.compile(
        r"according to the (article|page|webpage|website|wiki\w*)", re.IGNORECASE
    ),
    # General content fabrication
    re.compile(
        r"i (?:see|found|notice|read) the following (articles?|stories|headlines|results)",
        re.IGNORECASE,
    ),
    re.compile(r"here are the (results|findings|articles|stories)", re.IGNORECASE),
]


def check_fabricated_tool_output(
    response: str, *, had_tool_result: bool = False
) -> str | None:
    """Detect fabricated filesystem/tool responses when no real tool fired."""
    if had_tool_result:
        return None
    for pattern in _FABRICATED_TOOL_PATTERNS:
        if pattern.search(response):
            return (
                "You described file contents, directory listings, news headlines, or "
                "webpage content without actually fetching them. You can't know what's "
                "in a directory, news feed, or webpage unless you use a tool like "
                "[LIST_DIR:/path], [FETCH_RSS:feed], or [FETCH_WEBPAGE:url]. "
                "Don't fabricate results."
            )
    return None


def check_assistant_collapse(response: str) -> str | None:
    """Detect assistant-mode language that contradicts the being's identity."""
    response_lower = response.lower()
    for phrase in ASSISTANT_PHRASES:
        if phrase in response_lower:
            return (
                "You slipped into assistant mode. You're not submitting a draft. "
                "You don't say 'here is a revised' or 'how can I help' or offer "
                "services. Just think and speak naturally as yourself."
            )
    return None


def check_peer_sycophancy(response: str) -> str | None:
    """Detect mutual validation patterns that signal a degenerate agreement loop."""
    response_lower = response.lower()
    for phrase in SYCOPHANCY_PHRASES:
        if phrase in response_lower:
            return (
                "You're agreeing without adding anything. Don't just validate — "
                "push back, ask a real question, or say something concrete. "
                "What do you actually think that's different from what they said?"
            )
    return None


def run_layer1_reflexes(
    response: str,
    perception: str,
    identity: str,
    personality: str,
    *,
    had_tool_result: bool = False,
) -> tuple[bool, str | None]:
    checks = [
        check_hallucinated_senses(response, perception, identity, personality),
        check_third_person_human(response),
        check_narration(response),
        check_assistant_collapse(response),
        check_peer_sycophancy(response),
        check_fabricated_tool_output(response, had_tool_result=had_tool_result),
    ]
    corrections = [c for c in checks if c is not None]
    if corrections:
        return False, " ".join(corrections)
    return True, None


def run_layer2_heuristics(response: str, log_file: str) -> None:
    violations = []

    # Assistant collapse — now enforced in Layer 1, but still log if it slips through
    # (e.g. after max retries exhausted)
    response_lower = response.lower()
    for phrase in ASSISTANT_PHRASES:
        if phrase in response_lower:
            violations.append(f"assistant-collapse: matched '{phrase}'")
            break

    # Peer sycophancy — also enforced in Layer 1, log if it slips through
    for phrase in SYCOPHANCY_PHRASES:
        if phrase in response_lower:
            violations.append(f"peer-sycophancy: matched '{phrase}'")
            break

    # Excessive questions
    if response.count("?") > 1:
        violations.append(f"excessive-questions: {response.count('?')} question marks")

    # Too long
    word_count = len(response.split())
    if word_count > 150:
        violations.append(f"too-long: {word_count} words")

    if not violations:
        return

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    preview = response[:100].replace("\n", " ")
    with open(log_file, "a") as f:
        for v in violations:
            f.write(f'[{timestamp}] {v} | "{preview}..."\n')
