"""Binary intent system — curiosity detection and search via yes/no gate.

The model thinks in full language but outputs only yes/no at decision points.
This avoids the 50%+ failure rate of formatted tool calls on small models.
Validated at 92-95% accuracy over 400 trials (see experiments/binary_intent_test/).
"""

import asyncio
import logging
import re

import ollama

from config import CONTEXT_WINDOW, INTENT_MAX_RESULT_CHARS
from tools import tool_fetch_webpage, tool_fetch_rss
from brain.actions import _extract_topic, _topic_to_wikipedia_url, _topic_to_feed

logger = logging.getLogger("companion_daemon")


# ---------------------------------------------------------------------------
# A) Binary gate — synchronous (caller wraps in asyncio.to_thread)
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATES = {
    "standard": "[CONTEXT]\n{context}\n\n[QUESTION]\n{question}\n\n[RESPOND: yes or no]",
    "self_first": (
        "[CONTEXT]\n{context}\n\n"
        "[SELF-CHECK]\nConsider what serves YOU best right now, "
        "not what others might want.\n\n"
        "[QUESTION]\n{question}\n\n[RESPOND: yes or no]"
    ),
}

_YES_TOKENS = {"yes", "y", "1"}
_NO_TOKENS = {"no", "n", "0"}


def binary_gate(
    model: str, context: str, question: str, framing: str = "standard"
) -> bool:
    """Ask a yes/no question via the LLM. Returns True for yes, False otherwise."""
    template = _PROMPT_TEMPLATES.get(framing, _PROMPT_TEMPLATES["standard"])
    prompt = template.format(context=context, question=question)

    try:
        resp = ollama.generate(
            model=model,
            prompt=prompt,
            options={"temperature": 0.0, "num_ctx": CONTEXT_WINDOW, "num_predict": 1},
        )
        raw = resp.get("response", "").strip().lower()
        logger.debug("binary_gate raw output: %r", raw)
        return raw in _YES_TOKENS
    except Exception:
        logger.exception("binary_gate error")
        return False


# ---------------------------------------------------------------------------
# B) Curiosity detection — pure regex, no LLM
# ---------------------------------------------------------------------------

_CURIOSITY_PATTERNS = [
    (re.compile(r"\bi wonder (?:about|what|how|why|if)", re.IGNORECASE), "wikipedia"),
    (re.compile(r"\bwhat is ", re.IGNORECASE), "wikipedia"),
    (re.compile(r"\bwhat are ", re.IGNORECASE), "wikipedia"),
    (re.compile(r"\bi'?m curious about ", re.IGNORECASE), "wikipedia"),
    (
        re.compile(
            r"\bi want to (?:learn|know|understand|read) (?:about )?", re.IGNORECASE
        ),
        "wikipedia",
    ),
    (re.compile(r"\bcheck the news\b", re.IGNORECASE), "rss"),
    (re.compile(r"\bwhat'?s happening", re.IGNORECASE), "rss"),
    (re.compile(r"\bsearch for ", re.IGNORECASE), "web"),
    (re.compile(r"\blook up ", re.IGNORECASE), "web"),
    (
        re.compile(
            r"\bfind (?:information|articles|research) (?:on|about) ", re.IGNORECASE
        ),
        "web",
    ),
]

_VAGUE_TOPICS = {
    "something",
    "anything",
    "everything",
    "nothing",
    "stuff",
    "things",
    "it",
    "this",
    "that",
}

_NEGATION_PATTERNS = re.compile(
    r"i was |i had |yesterday|last time"
    r"|if i |would i |could i |should i "
    r"|i don'?t |i never "
    r"|the concept of (?:curiosity|wondering)",
    re.IGNORECASE,
)


def detect_curiosity(thought: str) -> dict | None:
    """Detect curiosity intent in a thought. Returns dict or None."""
    for pattern, search_type in _CURIOSITY_PATTERNS:
        match = pattern.search(thought)
        if not match:
            continue

        # Negation filter: check 100 chars before match
        pre_start = max(0, match.start() - 100)
        prefix = thought[pre_start : match.start()]
        if _NEGATION_PATTERNS.search(prefix):
            continue

        # RSS patterns don't need topic extraction
        if search_type == "rss":
            return {"topic": "news", "search_type": "rss", "confidence": 0.8}

        # Extract topic from text after the matched phrase
        topic = _extract_topic(thought, match.end())
        if len(topic) < 3 or topic.lower() in _VAGUE_TOPICS:
            continue

        return {
            "topic": topic,
            "search_type": search_type,
            "confidence": 0.85,
        }

    return None


# ---------------------------------------------------------------------------
# C) Process curiosity — async orchestrator
# ---------------------------------------------------------------------------


async def process_curiosity(
    model: str, being_context: str, curiosity: dict, framing: str = "standard"
) -> str | None:
    """Gate-check curiosity, then execute search. Returns formatted result or None."""
    topic = curiosity["topic"]
    search_type = curiosity["search_type"]

    question = f"Look up information about {topic} right now?"
    confirmed = await asyncio.to_thread(
        binary_gate,
        model,
        being_context,
        question,
        framing,
    )
    if not confirmed:
        logger.debug("binary_gate rejected search for %r", topic)
        return None

    try:
        if search_type in ("wikipedia", "web"):
            url = _topic_to_wikipedia_url(topic)
            content = await asyncio.to_thread(
                tool_fetch_webpage,
                url,
                INTENT_MAX_RESULT_CHARS,
            )
        else:  # rss
            feed_name = _topic_to_feed(topic)
            content = await asyncio.to_thread(tool_fetch_rss, feed_name)
    except Exception:
        logger.exception("process_curiosity fetch error for %r", topic)
        return None

    if not content or content.startswith("Error"):
        return None

    content = content[:INTENT_MAX_RESULT_CHARS]
    return f"[Search result for '{topic}']\n{content}\n[End of search result]"
