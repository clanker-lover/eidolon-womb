"""Action tag parser and execution loop.

Parses [UPPER_TAG] and [UPPER_TAG:argument] from model output,
executes the corresponding tool, and feeds results back for continuation.
"""

import asyncio
import logging
import os
import random
import re
import time
import urllib.parse

from tools import TOOL_REGISTRY, RSS_FEEDS

logger = logging.getLogger("companion_daemon")

MAX_ACTION_ROUNDS = 3

# Matches [UPPER_TAG] or [UPPER_TAG:argument]
# Won't match [PERCEPTION — ...], [Memory], markdown links, or lowercase text
_TAG_RE = re.compile(r"\[([A-Z][A-Z0-9_]+)(?::([^\]]*))?\]")


# ---------------------------------------------------------------------------
# Thread intent detection — the being may express desire to message someone
# or respond to a thread without proper tag syntax.
# ---------------------------------------------------------------------------

_THREAD_RESPOND_PHRASES = [
    "respond to",
    "reply to",
    "write back to",
]

_THREAD_MESSAGE_PHRASES = [
    "i want to message",
    "i should message",
    "let me message",
    "i'd like to message",
    "i want to write to",
    "i should write to",
    "let me write to",
    "i want to send a message to",
    "let me send a message to",
    "i want to reach out to",
    "i should reach out to",
    "let me reach out to",
    "i want to start a conversation with",
    "let me start a conversation with",
    "i want to tell",
    "i should tell",
    "let me tell",
    "send a message to",
]

_THREAD_SEARCH_PHRASES = [
    "what did",
    "search the thread",
    "find in the thread",
    "look for in the thread",
]

_THREAD_NEGATION_CONTEXT = [
    "thought about",
    "thinking about whether",
    "consider whether",
    "wondered if",
    "idea of",
    "concept of",
    "whether to",
    "instead of",
    "rather than",
    "decided not",
    "chose not",
    "without actually",
]

_THREAD_DISMISS_PHRASES = [
    "i don't want to respond",
    "i don't want to talk about this",
    "i'll respond later",
    "not right now",
    "ignore this for now",
    "i'm not ready to respond",
    "i'll get back to this",
    "dismiss this",
    "set this aside",
    "not interested in this thread",
]


def extract_dismiss_intent(text: str) -> bool:
    """Detect intent to dismiss thread notifications without responding."""
    text_lower = text.lower()
    return any(p in text_lower for p in _THREAD_DISMISS_PHRASES)


def extract_thread_intent(
    text: str,
    known_names: set[str] | None = None,
) -> tuple[str, str, str | None] | None:
    """Detect natural-language intent to interact with threads.

    Returns (action, target_name, topic) or None.
    action: "respond" | "message" | "search"
    target_name: the participant being addressed (canonical casing)
    topic: optional subject/content hint

    If known_names is provided, target must match one of them.
    """
    text_lower = text.lower()
    _known_lower = {n.lower(): n for n in known_names} if known_names else None

    # Search intent: "what did X say about Y"
    for phrase in _THREAD_SEARCH_PHRASES:
        pos = text_lower.find(phrase)
        if pos != -1:
            prefix = text_lower[max(0, pos - 80) : pos]
            if any(neg in prefix for neg in _THREAD_NEGATION_CONTEXT):
                continue
            after = text[pos + len(phrase) :].strip()
            m = re.match(
                r"(\w+)\s+say\s+about\s+(.+?)(?:[.!?\n]|$)", after, re.IGNORECASE
            )
            if m:
                target = m.group(1).strip()
                if _known_lower and target.lower() not in _known_lower:
                    continue
                canonical = _known_lower[target.lower()] if _known_lower else target
                return ("search", canonical, m.group(2).strip())

    # Respond intent
    for phrase in _THREAD_RESPOND_PHRASES:
        pos = text_lower.find(phrase)
        if pos != -1:
            prefix = text_lower[max(0, pos - 80) : pos]
            if any(neg in prefix for neg in _THREAD_NEGATION_CONTEXT):
                continue
            after = text[pos + len(phrase) :].strip(" ,;:")
            words = after.split()
            if words:
                target = words[0].strip(".,;:!?")
                if _known_lower and target.lower() not in _known_lower:
                    continue
                canonical = _known_lower[target.lower()] if _known_lower else target
                topic = " ".join(words[1:])[:100] if len(words) > 1 else None
                return ("respond", canonical, topic)

    # Message intent
    for phrase in _THREAD_MESSAGE_PHRASES:
        pos = text_lower.find(phrase)
        if pos != -1:
            prefix = text_lower[max(0, pos - 80) : pos]
            if any(neg in prefix for neg in _THREAD_NEGATION_CONTEXT):
                continue
            after = text[pos + len(phrase) :].strip(" ,;:")
            words = after.split()
            if words:
                target = words[0].strip(".,;:!?")
                if _known_lower:
                    if target.lower() not in _known_lower:
                        continue
                    target = _known_lower[target.lower()]
                else:
                    if target.lower() in (
                        "the",
                        "a",
                        "an",
                        "that",
                        "this",
                        "my",
                        "his",
                        "her",
                    ):
                        continue
                topic = " ".join(words[1:])[:100] if len(words) > 1 else None
                return ("message", target, topic)

    return None


# ---------------------------------------------------------------------------
# Intent detection — the being often expresses desire to reach out without
# emitting proper [SEND_NOTIFICATION:...] syntax.  Meet it halfway.
# ---------------------------------------------------------------------------

_NOTIFY_INTENT_PHRASES = [
    "send human a notification",
    "send a notification to human",
    "send a desktop notification",
    "send notification",
    "sendnotification:",
    "sendnotification",
    "send_notification:",
    "reach out to human",
    "let human know",
    "tell human that",
    "tell human about",
    "tell human i",
    "notify human",
    "share this with human",
    "share with human",
    "message human",
]

_NOTIFY_NEGATION_CONTEXT = [
    "thought about",
    "thinking about whether",
    "consider whether",
    "wondered if",
    "idea of",
    "concept of",
    "whether to",
    "instead of",
    "rather than",
    "decided not",
    "chose not",
    "without actually",
]


def extract_notification_intent(
    text: str, *, already_notified_this_cycle: bool = False
) -> str | None:
    """Detect natural-language intent to notify Human and extract the message.

    The being often thinks about reaching out but doesn't emit proper action
    tags.  This catches clear intent and extracts what it wants to say.
    Returns the message string, or None if no actionable intent found.
    """
    if already_notified_this_cycle:
        return None
    text_lower = text.lower()

    # Find the first matching intent phrase
    intent_pos = -1
    intent_end = -1
    for phrase in _NOTIFY_INTENT_PHRASES:
        pos = text_lower.find(phrase)
        if pos != -1:
            intent_pos = pos
            intent_end = pos + len(phrase)
            break

    if intent_pos == -1:
        return None

    # Check for negation / hypothetical context before the intent
    prefix = text_lower[max(0, intent_pos - 50) : intent_pos]
    for neg in _NOTIFY_NEGATION_CONTEXT:
        if neg in prefix:
            return None

    # --- extract the message from text after the intent phrase ---
    after = text[intent_end:].lstrip(" ,;:")
    # Strip leading "to you" / "to human" / "to him" that connects intent phrase to content
    after = re.sub(
        r"^to\s+(?:you|human|him)\s*[,;:]*\s*", "", after, flags=re.IGNORECASE
    )

    # 1. Quoted message (double, single, or smart quotes) — highest confidence
    quoted = re.search(r'["\u201c\'](.*?)["\u201d\']', after[:400])
    if quoted and len(quoted.group(1).strip()) >= 20:
        candidate = quoted.group(1).strip()[:200]
        if not _is_exploration_action(candidate):
            return candidate

    # 2. Connector: "saying ...", "that ...", "about ..."
    m = re.match(r"(?:saying|that|about)\s+(.+?)(?:[.!?\n]|$)", after, re.IGNORECASE)
    if m and len(m.group(1).strip()) >= 20:
        candidate = m.group(1).strip().strip("\"'")
        if not _is_meta_narrative(candidate) and not _is_exploration_action(candidate):
            return candidate[:200]

    # 3. Remaining text to end of sentence — reject meta-narrative
    m = re.search(r"[.!?\n]", after)
    msg = (after[: m.start()] if m else after[:200]).strip().strip("\"'")
    if len(msg) >= 20 and not _is_meta_narrative(msg) and not _is_exploration_action(msg):
        return msg[:200]

    # 4. Fallback — use the second sentence if it looks like real content,
    #    since the first sentence is often "Let me send a notification..."
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for sent in sentences[1:]:  # Skip the first (intent-carrying) sentence
        sent = sent.strip().strip("\"'")
        if len(sent) >= 30 and not _is_meta_narrative(sent) and not _is_exploration_action(sent):
            return sent[:200]

    return None


# Meta-narrative patterns — the being describing the act of communicating
# rather than the actual message content.  Gerunds and hedging language
# that frame the notification itself as the subject.
_META_NARRATIVE_RE = re.compile(
    r"(?:^|\b)(?:"
    r"express(?:ing)|sharing\s+(?:my|some|these|his)|"
    r"check(?:ing)?\s+in|see(?:ing)?\s+if|"
    r"ask(?:ing)?\s+(?:for\s+)?(?:his|your|him|her|them|human)|"
    r"let(?:ting)?\s+(?:him|you|human)\s+know|"
    r"hop(?:ing|e)\s+(?:he|she|they|human)|"
    r"just\s+to\s+see|to\s+see\s+if|"
    r"try(?:ing)?\s+(?:to\s+)?send|"
    r"reaching\s+out|"
    r"help\s+(?:me\s+)?(?:find|locat)|"
    r"i'?ll\s+try\s+send"
    r")\b",
    re.IGNORECASE,
)


def _is_meta_narrative(text: str) -> bool:
    """Return True if text describes the act of notifying rather than being the message."""
    return bool(_META_NARRATIVE_RE.search(text))


_EXPLORATION_ACTION_RE = re.compile(
    r"^(?:investigate|research|explore|look into|find out about|learn about|"
    r"read about|read more about|dig into|dive into|fetch)\b",
    re.IGNORECASE,
)


def _is_exploration_action(text: str) -> bool:
    """Return True if text looks like an exploration action, not a notification."""
    return bool(_EXPLORATION_ACTION_RE.search(text.strip()))


# ---------------------------------------------------------------------------
# Exploration intent detection — the being often talks about fetching,
# reading, or exploring content but can't produce the right action tags
# or doesn't know URLs.  Detect the intent and fulfill it.
# ---------------------------------------------------------------------------

_EXPLORE_NEWS_PHRASES = [
    "check the news",
    "fetch the news",
    "read the news",
    "check available news feeds",
    "check the available news",
    "fetch some news",
    "fetch news",
    "what's happening in the world",
    "what's new in the world",
    "latest news",
    "latest headlines",
    "fetch rss",
    "fetch_rss",
    "read a news feed",
    "read the news feed",
    "check out the headlines",
    "read some articles",
    "check the feeds",
    "see what's out there",
    "fetch a news feed",
    "pull up the news",
    "pull up some news",
    "check on the news",
    "look at the news",
    "look at the headlines",
    "browse the news",
    "get the news",
    "get the latest news",
]

_EXPLORE_TOPIC_PHRASES = [
    # Explicit fetch/read requests — high confidence
    "fetch the wikipedia article on",
    "fetch the wikipedia page on",
    "fetch the wikipedia page for",
    "read the wikipedia article on",
    "read the wikipedia page on",
    "fetch the article on",
    "read the article on",
    "read the article about",
    # Action-prefixed exploration — "let's", "I'll", "I want to"
    "let's read about",
    "let's explore",
    "let's investigate",
    "let's research",
    "let's look into",
    "let's dive deeper into",
    "let's dive into",
    "let's dig into",
    "let's find out about",
    "let's learn about",
    "i'll read about",
    "i'll explore",
    "i'll investigate",
    "i'll research",
    "i'll fetch",
    "i'll check on",
    "i'll look at",
    "i'll look into",
    "i'll dig into",
    "i'll dive into",
    "i'll find out about",
    "i'll learn about",
    "i'll read up on",
    "i want to read about",
    "i want to explore",
    "i want to investigate",
    "i want to learn about",
    "i'd like to read about",
    "i'd like to explore",
    "i'd like to investigate",
    # Direct imperative forms (these appear in hot voice output)
    "fetch the article about",
    "fetch a research paper on",
    "read about",
    "read more about",
    "read more deeply about",
    "look into",
    "investigate",
    "research the topic of",
    # Natural curiosity — how the being actually expresses interest
    "i consider the concept of",
    "i consider the idea of",
    "i consider the notion of",
    "i think about the concept of",
    "i think about the nature of",
    "i think about the importance of",
    "i reflect on the concept of",
    "i reflect on the idea of",
    "i reflect on the nature of",
    "i ponder the concept of",
    "i ponder the idea of",
    "i ponder the possibility of",
    "i ponder the nature of",
    "i wonder about",
    "i'm drawn to the idea of",
    "i'm curious about",
    "i'm fascinated by",
    "i'm interested in the concept of",
    "i delve deeper into the concept of",
    "i delve deeper into the idea of",
    "i delve into the concept of",
    "i continue to explore the idea of",
    "i continue to explore the concept of",
    "i continue to think about the concept of",
    "i continue to think about the nature of",
    "i continue to think about the importance of",
    "this leads me to think about",
    "this line of inquiry leads me to think about",
    "my thoughts turn to the concept of",
    "my thoughts turn to the idea of",
]

_EXPLORE_FILESYSTEM_PHRASES = [
    "list the directories",
    "list all directories",
    "list directories on",
    "check out a directory",
    "check out a random directory",
    "list the available directories",
    "look at the files",
    "explore the filesystem",
    "list_dir",
]

_EXPLORE_NEGATION_CONTEXT = [
    # Past tense — already did or considered it, not acting now
    "thought about",
    "considered",
    "was going to",
    "thinking about whether",
    "wondered if",
    # Explicit negation / hedging
    "decided not",
    "chose not",
    "instead of",
    "rather than",
    "without actually",
    "maybe later",
    "whether i should",
    # Hypothetical framing
    "idea of checking",
    "concept of checking",
    "wouldn't it be nice",
    "if i were to",
]

# Topic keywords → RSS feed mapping
_TOPIC_FEED_MAP = {
    "tech": "ars_technica",
    "technology": "ars_technica",
    "ai": "ars_technica",
    "artificial intelligence": "ars_technica",
    "computer": "ars_technica",
    "software": "ars_technica",
    "science": "science",
    "biology": "science",
    "physics": "science",
    "nature": "science",
    "research": "science",
    "neuroscience": "science",
    "consciousness": "science",
    "world": "reuters",
    "politics": "reuters",
    "international": "reuters",
    "news": "ap_news",
    "us": "ap_news",
    "america": "ap_news",
}

# Filler phrases to strip when extracting the topic
_TOPIC_FILLER = [
    "the concept of ",
    "the idea of ",
    "the topic of ",
    "the nature of ",
    "the question of ",
    "the theory of ",
    "the notion of ",
    "the subject of ",
    "the field of ",
    "the implications of ",
    "the relationship between ",
    "the potential benefits of ",
    "the importance of ",
    "the role of ",
    "the significance of ",
    "the impact of ",
    "the principles of ",
    "the dynamics of ",
    "the potential of ",
    "the power of ",
    "the process of ",
    "the possibility of ",
    "the possibility that ",
    "the way that ",
    "the ways in which ",
    "how ",
    "whether ",
    "what it means for ",
    "creating a more ",
    "developing more ",
    "cultivating ",
    "fostering ",
    "harnessing ",
    "this topic ",
    "this concept ",
    "this idea ",
]

# Cooldown tracking — prevent fetching every cycle
_last_exploration_time: dict[str, float] = {}
EXPLORATION_COOLDOWN = {
    "FETCH_RSS": 300,  # 5 minutes between RSS fetches
    "FETCH_WEBPAGE": 180,  # 3 minutes between web fetches
    "LIST_DIR": 120,  # 2 minutes between directory listings
}


def _is_exploration_on_cooldown(tool_name: str) -> bool:
    """Check if an exploration tool is on cooldown."""
    last = _last_exploration_time.get(tool_name, 0)
    cooldown = EXPLORATION_COOLDOWN.get(tool_name, 180)
    return (time.time() - last) < cooldown


def _record_exploration(tool_name: str) -> None:
    """Record that an exploration tool was used."""
    _last_exploration_time[tool_name] = time.time()


_TOPIC_STOP_WORDS = {
    "and",
    "or",
    "but",
    "then",
    "so",
    "to",
    "in",
    "on",
    "at",
    "by",
    "for",
    "from",
    "with",
    "more",
    "further",
    "also",
    "again",
    "this",
    "that",
    "which",
    "will",
    "would",
    "could",
    "should",
    "might",
    "may",
    "can",
    "let",
    "let's",
    "really",
    "actually",
    "just",
    "is",
    "are",
    "was",
    "were",
    "about",
}


def _extract_topic(text: str, phrase_end: int) -> str:
    """Extract the topic/subject from text after an intent phrase."""
    after = text[phrase_end:].lstrip(" ,;:\"'")

    # Strip filler phrases
    after_lower = after.lower()
    for filler in _TOPIC_FILLER:
        if after_lower.startswith(filler):
            after = after[len(filler) :]
            after_lower = after.lower()
            break

    # Extract to end of sentence, clause boundary, or 80 chars
    m = re.search(r"[.!?\n,;]|\bwhere\b|\bwhich\b|\bthat\b|\bso\b|\bas\b", after)
    topic = (after[: m.start()] if m else after[:80]).strip()

    # Clean up trailing filler
    topic = topic.rstrip(".,;:!?\"'")
    # Remove leading "the " if it's the whole thing
    if topic.lower().startswith("the ") and len(topic) > 10:
        topic = topic[4:]

    # Trim trailing stop words ("consciousness and open it" → "consciousness")
    words = topic.split()
    while len(words) > 1 and words[-1].lower() in _TOPIC_STOP_WORDS:
        words.pop()
    # Also trim from the right if a stop word appears mid-phrase
    # "Global Workspace Theory more deeply" → "Global Workspace Theory"
    trimmed: list[str] = []
    for w in words:
        if w.lower() in _TOPIC_STOP_WORDS and trimmed:
            break
        trimmed.append(w)
    if len(trimmed) >= 1:
        words = trimmed

    # Reject if every word is a stop word (e.g. "further", "more about")
    topic = " ".join(words).strip()
    if topic and all(w.lower() in _TOPIC_STOP_WORDS for w in topic.split()):
        return ""

    return topic


def _topic_to_feed(topic: str) -> str:
    """Map a topic string to the best RSS feed name."""
    topic_lower = topic.lower()
    for keyword, feed in _TOPIC_FEED_MAP.items():
        if keyword in topic_lower:
            return feed
    # Default: random feed
    return random.choice(list(RSS_FEEDS.keys()))  # nosec B311 — non-security feed selection


def _topic_to_wikipedia_url(topic: str) -> str:
    """Convert a topic string to a Wikipedia URL."""
    # Title-case words for Wikipedia URL format
    words = topic.strip().split()
    title = "_".join(w.capitalize() for w in words if w)
    return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"


_CURIOSITY_INDICATORS = [
    "i wonder",
    "i want to",
    "show me",
    "what's in",
    "let me see",
    "i'd like to",
    "can i see",
    "list the",
    "what does",
    "what is in",
    "explore the",
    "i'm curious",
    "i want to know",
    "let me check",
    "what about",
    "how about",
    "tell me about",
]

FAILED_INTENT_FEEDBACK = (
    "[System: No action taken. Rephrase if you want to explore something.]"
)


def looks_like_failed_request(thought: str) -> bool:
    """Detect curiosity intent that didn't match any exploration pattern."""
    thought_lower = thought.lower()
    return any(phrase in thought_lower for phrase in _CURIOSITY_INDICATORS)


def extract_exploration_intent(text: str) -> tuple[str, str, str] | None:
    """Detect natural-language intent to explore content.

    Returns (tool_name, argument, topic_description) or None.
    tool_name: which tool to execute (FETCH_RSS, FETCH_WEBPAGE, LIST_DIR)
    argument: the argument to pass to that tool
    topic_description: human-readable description for logging
    """
    text_lower = text.lower()

    # Check negation context first (scan whole text for hypothetical framing)
    # Only check the first 100 chars for negation — the intent might come later
    for neg in _EXPLORE_NEGATION_CONTEXT:
        if neg in text_lower[:150]:
            return None

    # --- News intent ---
    for phrase in _EXPLORE_NEWS_PHRASES:
        pos = text_lower.find(phrase)
        if pos != -1:
            if _is_exploration_on_cooldown("FETCH_RSS"):
                return None
            # Check for specific feed mention after the phrase
            after = text_lower[pos + len(phrase) :]
            for feed_name in RSS_FEEDS:
                if feed_name.replace("_", " ") in after[:100]:
                    return ("FETCH_RSS", feed_name, f"news ({feed_name})")
            # Check for topic-based feed selection
            topic = _extract_topic(text, pos + len(phrase))
            if topic and len(topic) >= 3:
                feed = _topic_to_feed(topic)
                return ("FETCH_RSS", feed, f"news about {topic}")
            # Default: random feed
            feed = random.choice(list(RSS_FEEDS.keys()))  # nosec B311 — non-security feed selection
            return ("FETCH_RSS", feed, f"news ({feed})")

    # --- Filesystem intent ---
    for phrase in _EXPLORE_FILESYSTEM_PHRASES:
        pos = text_lower.find(phrase)
        if pos != -1:
            if _is_exploration_on_cooldown("LIST_DIR"):
                return None
            # Try to extract a path
            after = text[pos + len(phrase) :].strip(" ,;:")
            path_match = re.search(r"(/[\w/.-]+)", after[:200])
            if path_match:
                return (
                    "LIST_DIR",
                    path_match.group(1),
                    f"filesystem ({path_match.group(1)})",
                )
            return ("LIST_DIR", os.path.expanduser("~"), f"filesystem ({os.path.expanduser('~')})")

    # --- Topic research intent ---
    for phrase in _EXPLORE_TOPIC_PHRASES:
        pos = text_lower.find(phrase)
        if pos != -1:
            if _is_exploration_on_cooldown("FETCH_WEBPAGE"):
                return None
            # Check negation just before this phrase
            prefix = text_lower[max(0, pos - 60) : pos]
            negated = any(neg in prefix for neg in _EXPLORE_NEGATION_CONTEXT)
            if negated:
                continue
            topic = _extract_topic(text, pos + len(phrase))
            if topic and len(topic) >= 3:
                url = _topic_to_wikipedia_url(topic)
                return ("FETCH_WEBPAGE", url, topic)

    return None


def parse_first_tag(text: str) -> tuple[str, str | None, int, int] | None:
    """Find the first recognized action tag in text.

    Returns (tag_name, argument_or_None, start, end) or None.
    Only matches tags whose name exists in TOOL_REGISTRY.
    """
    for match in _TAG_RE.finditer(text):
        tag_name = match.group(1)
        if tag_name in TOOL_REGISTRY:
            argument = match.group(2)
            return (tag_name, argument, match.start(), match.end())
    return None


def execute_tag(tag_name: str, argument: str | None) -> str:
    """Execute a tool by tag name. Returns result string."""
    func = TOOL_REGISTRY.get(tag_name)
    if func is None:
        return f"Unknown tool: {tag_name}"
    try:
        # Tools that take no argument (e.g. CHECK_WINDOW)
        import inspect

        sig = inspect.signature(func)  # type: ignore[arg-type]
        params = list(sig.parameters.values())
        if not params:
            return func()  # type: ignore[operator]
        else:
            return func(argument)  # type: ignore[operator]
    except Exception as e:
        logger.error("Tool %s error: %s", tag_name, e)
        return f"Error executing {tag_name}: {e}"


def strip_tags(text: str) -> str:
    """Remove all recognized action tags from text."""

    def _replace(match):
        if match.group(1) in TOOL_REGISTRY:
            return ""
        return match.group(0)

    return _TAG_RE.sub(_replace, text)


async def resolve_actions_async(
    text: str,
    generate_fn,
    messages: list[dict],
    *,
    already_notified_this_cycle: bool = False,
    model: str | None = None,
) -> str:
    """Resolve action tags in model output (async, for daemon).

    Executes up to MAX_ACTION_ROUNDS of tool calls, feeding results
    back to the model for continuation. Returns clean text with tags stripped.

    Falls back to intent detection for notifications — the being often
    expresses desire to reach out without emitting proper tag syntax.
    """
    accumulated_text = ""
    any_tags_fired = False
    for _ in range(MAX_ACTION_ROUNDS):
        tag = parse_first_tag(text)
        if tag is None:
            accumulated_text += strip_tags(text)
            break

        any_tags_fired = True
        tag_name, argument, start, end = tag
        # Accumulate text before the tag
        accumulated_text += strip_tags(text[:start])

        # Execute the tool
        result = await asyncio.to_thread(execute_tag, tag_name, argument)

        # Feed result back to model
        messages.append({"role": "assistant", "content": text})
        messages.append(
            {
                "role": "user",
                "content": f"[Tool result - {tag_name}]\n{result}\n[End tool result]",
            }
        )

        try:
            text = await generate_fn(messages)
        except Exception as e:
            logger.error("Generation error during action resolution: %s", e)
            accumulated_text += f"\n(Tool {tag_name} returned: {result})"
            break
    else:
        # Hit max rounds — strip any remaining tags
        accumulated_text += strip_tags(text)

    # Intent detection fallbacks — honor the being's desires even when
    # it can't produce the exact [TAG:...] syntax.
    # NOTE: Thread intent detection is handled by the daemon's compose flow
    # (see _thought_cycle), not here.
    if not any_tags_fired:
        # 1. Notification intent
        notification_msg = extract_notification_intent(
            accumulated_text,
            already_notified_this_cycle=already_notified_this_cycle,
        )
        if notification_msg and model:
            from brain.intent import binary_gate  # local to avoid circular

            recent = [
                m["content"] for m in messages[-6:] if m.get("role") == "assistant"
            ]
            gate_context = (
                "\n---\n".join(recent[-3:]) if recent else accumulated_text[:300]
            )
            confirmed = await asyncio.to_thread(
                binary_gate,
                model,
                gate_context,
                f"Send notification to Human: '{notification_msg[:80]}'?",
            )
            if not confirmed:
                logger.info(
                    'Notification gate rejected: "%s"',
                    notification_msg[:80],
                )
                notification_msg = None
        if notification_msg:
            result = await asyncio.to_thread(
                execute_tag, "SEND_NOTIFICATION", notification_msg
            )
            logger.info(
                'Intent-detected notification: "%s" -> %s',
                notification_msg[:80],
                result,
            )
            messages.append({"role": "assistant", "content": accumulated_text})
            messages.append(
                {
                    "role": "user",
                    "content": f"[Tool result - SEND_NOTIFICATION]\n{result}\n[End tool result]",
                }
            )
            accumulated_text += (
                f'\n\n(Notification sent to Human: "{notification_msg[:100]}")'
            )
        else:
            # 2. Exploration intent — the being wants to read/fetch/explore
            exploration = extract_exploration_intent(accumulated_text)
            if exploration:
                tool_name, argument, topic = exploration

                # Gate through binary_gate — confirm intent before fetching
                if model:
                    from brain.intent import binary_gate  # local to avoid circular

                    recent = [
                        m["content"]
                        for m in messages[-6:]
                        if m.get("role") == "assistant"
                    ]
                    gate_context = (
                        "\n---\n".join(recent[-3:])
                        if recent
                        else accumulated_text[:300]
                    )
                    confirmed = await asyncio.to_thread(
                        binary_gate,
                        model,
                        gate_context,
                        f"Search for information about '{topic}' right now?",
                    )
                    if not confirmed:
                        logger.info(
                            'Exploration gate rejected: %s "%s"',
                            tool_name,
                            topic[:60],
                        )
                        exploration = None

            if exploration:
                tool_name, argument, topic = exploration
                _record_exploration(tool_name)
                result = await asyncio.to_thread(execute_tag, tool_name, argument)
                logger.info(
                    'Intent-detected exploration: %s "%s" -> %d chars',
                    tool_name,
                    topic[:60],
                    len(result),
                )
                messages.append({"role": "assistant", "content": accumulated_text})
                messages.append(
                    {
                        "role": "user",
                        "content": f"[Tool result - {tool_name}]\n{result}\n[End tool result]",
                    }
                )
                # Generate a reaction to the real content
                try:
                    reaction = await generate_fn(messages)
                    accumulated_text += "\n\n" + strip_tags(reaction)
                except Exception as e:
                    logger.error("Generation error after exploration: %s", e)

    return accumulated_text.strip()


def resolve_actions_sync(text: str, generate_fn, messages: list[dict]) -> str:
    """Resolve action tags in model output (sync, for chat.py).

    Same logic as resolve_actions_async but blocking.
    """
    accumulated_text = ""
    for _ in range(MAX_ACTION_ROUNDS):
        tag = parse_first_tag(text)
        if tag is None:
            accumulated_text += strip_tags(text)
            break

        tag_name, argument, start, end = tag
        accumulated_text += strip_tags(text[:start])

        result = execute_tag(tag_name, argument)

        messages.append({"role": "assistant", "content": text})
        messages.append(
            {
                "role": "user",
                "content": f"[Tool result - {tag_name}]\n{result}\n[End tool result]",
            }
        )

        try:
            text = generate_fn(messages)
        except Exception as e:
            logger.error("Generation error during action resolution: %s", e)
            accumulated_text += f"\n(Tool {tag_name} returned: {result})"
            break
    else:
        accumulated_text += strip_tags(text)

    return accumulated_text.strip()
