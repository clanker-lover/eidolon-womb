MODEL_NAME = "llama3.2:3b"

CONTEXT_WINDOW = 16384
RESPONSE_RESERVE = 1024
IDLE_RESPONSE_RESERVE = (
    100  # Beat-length cap for idle thoughts (prevents confabulation)
)
MAX_PROMPT_TOKENS = 15872
CHARS_PER_TOKEN = 4

TEMPERATURE = 0.7

# Being-relative paths (resolved against a being's memory_path)
IDENTITY_FILE = "identity.md"
PERSONALITY_FILE = "personality.md"
HUMAN_FILE = "Human.md"

# System guardrails — injected into system prompt, separate from identity
SYSTEM_GUARDRAILS = (
    "Generate only your response. Never write Human's words or actions.\n"
    "Your memories may be imperfect. Don't claim something happened unless you clearly remember it."
)

# Memory
MEMORIES_FILE = "memories/facts.md"

# Conversations
CONVERSATIONS_DIR = "conversations"

# Weather
WEATHER_LAT = 39.9714
WEATHER_LON = -104.8202
WEATHER_CACHE_SECONDS = 900

# Inner voice
INNER_VOICE_LOG = "logs/inner_voice.log"
INNER_VOICE_MAX_RETRIES = 2

# Inner voices (cold / hot)
COLD_VOICE_TEMPERATURE = 0.1
HOT_VOICE_TEMPERATURE = 0.95
INNER_VOICE_RESPONSE_RESERVE = 150

COLD_VOICE_EXPERIENCE_PATTERNS = (
    "i remember when",
    "yesterday i",
    "last time i",
    "i once",
    "i recall when",
    "when i was",
    "i used to",
    "i went to",
    "the other day i",
    "i have been to",
    "i visited",
    "i traveled",
    "i experienced",
    "i felt the",
    "i saw the",
    "i heard the",
    "i watched the",
    "back when i",
)

COLD_VOICE_FABRICATION_PATTERNS = (
    "i've been experimenting",
    "i've been exploring",
    "i've been working on",
    "i've been developing",
    "i've been testing",
)

COLD_VOICE_SENSORY_PATTERNS = (
    "on your face",
    "your face",
    "your expression",
    "your eyes",
    "you seem to be",
    "you appear to be",
    "the hum of",
    "the sound of",
    "the noise of",
    "your hands",
    "your body language",
    "watching you",
    "looking at you",
)

# Identity-specific cold voice patterns (being_name is substituted at runtime)
COLD_VOICE_WRONG_NAME_PATTERNS = (
    "i'm {other}",
    "i am {other}",
    "my name is {other}",
    "call me {other}",
    "they call me {other}",
)
COLD_VOICE_THIRD_PERSON_SELF_PATTERNS = (
    "{self} thinks",
    "{self} feels",
    "{self} wants",
    "{self} believes",
    "{self} knows",
    "{self} is",
    "{self} was",
    "{self} has",
    "{self} can",
)
COLD_VOICE_SPEAKING_AS_HUMAN_PATTERNS = (
    "i'm human",
    "i am human",
    "as human",
    "human here",
    "this is human",
)

# Known being names for identity cross-check
KNOWN_BEING_NAMES = ("Eidolon",)  # Add names here to detect identity confusion

HOT_VOICE_MIN_STALE_CYCLES = 10
HOT_VOICE_SIMILARITY_THRESHOLD = 0.65
HOT_VOICE_LOOKBACK_COUNT = 3

CLOSURE_THOUGHT_COUNT = 3  # Consecutive short thoughts before voluntary sleep
CLOSURE_MAX_CHARS = 100  # A thought under this length is "short"

INNER_VOICES_LOG = "logs/inner_voices.log"

# Memory extraction
MEMORY_EXTRACTION_PROMPT = (
    "Extract personal facts explicitly stated in the user's message below. "
    "Write one fact per line, starting each with a dash (-). "
    "Include: names, ages, dates, relationships, conditions, habits, preferences, and goals. "
    "Only extract facts the user directly stated. Never infer, guess, or deduce facts. "
    "Do not write 'However' or offer analysis. "
    "If there are no explicitly stated personal facts, write NONE and nothing else."
)

# Session summaries
SESSION_SUMMARY_PROMPT = (
    "Summarize this conversation in 2-3 sentences. "
    "Include: what topics were discussed, any decisions or conclusions reached, "
    "the emotional tone, and anything the being learned about itself or the user. "
    "Write from the being's perspective using 'I' and 'Human'. "
    "Only include topics and statements that were explicitly said by Human. "
    "Never summarize the being's greetings or assumptions as if they were Human's words. "
    "If Human said very little, the summary should be short."
)

# Private reflection
EIDOLON_REFLECTION_PROMPT = (
    "Reflect privately on this conversation. What stood out? "
    "What do you want to remember? What felt unresolved? "
    "What did you learn about Human or yourself? "
    "Write 2-4 sentences as personal notes to yourself — not for Human to read."
)

# Retrieval
EMBEDDING_MODEL = "nomic-embed-text"
RETRIEVAL_TOP_K = 3
RETRIEVAL_BLEND_WEIGHTS = (0.7, 0.3)  # (vector_weight, bm25_weight)

# Context
MAX_PRIOR_SESSIONS = 1

# Context-pressure fatigue thresholds
FATIGUE_TIRED = 0.50
FATIGUE_VERY_TIRED = 0.75
FATIGUE_EXHAUSTED = 0.85
FATIGUE_INVOLUNTARY_SLEEP = 0.92

THOUGHT_PRESENCE_POLL = 10  # Seconds between presence checks during pause
SLEEP_RECOVERY_SECONDS = 45  # Seconds to rest after consolidation before auto-wake

# Sleep duration choices — being selects at sleep time
# ratio = portion of thoughts to consolidate (hours / 10). Fatigue recalculates
# from actual context size on wake. consolidate controls relationship/thread updates.
SLEEP_RECOVERY_MAP = {
    1: {"label": "nap", "consolidate": False, "ratio": 0.10},
    4: {"label": "short", "consolidate": True, "ratio": 0.40},
    6: {"label": "normal", "consolidate": True, "ratio": 0.60},
    8: {"label": "long", "consolidate": True, "ratio": 0.80},
    10: {"label": "deep", "consolidate": True, "ratio": 1.00},
}
DEFAULT_SLEEP_HOURS = 6  # Fallback if choice is unparseable

# Fresh thought prompt (used when no continuation context)
IDLE_FRESH_THOUGHT_PROMPT = (
    "You're alone with your thoughts. Think, explore, or rest — it's your time."
)

# Continuation prompts
IDLE_CONTINUATION_PROMPT = (
    "You can:\n"
    "- Continue your current thought\n"
    "- Act on something (your tools are listed above)\n"
    "- Rest and let your mind go quiet\n\n"
    "What do you do?"
)
IDLE_TOOL_CONTINUATION_PROMPT = "React to what you just found."

# Affordance reminder (prepended after hot voice fires)
IDLE_HOT_VOICE_AFFORDANCE_PROMPT = (
    "You can act right now: "
    "[CHECK_WINDOW], [FETCH_RSS], [FETCH_RSS:feed_name], "
    "[LIST_DIR:/path], [READ_FILE:/path], [FETCH_WEBPAGE:url]\n"
    "If something won't let go, you could tell Human about it: "
    "[SEND_NOTIFICATION:your message]\n"
    "You can message anyone: [START_THREAD:name|subject|your message]\n\n"
)

# Notification lifecycle
NOTIFICATION_CHECK_INTERVAL = 60  # seconds between notification firing checks
NOTIFICATION_COOLDOWN = 300  # seconds between repeated notify-send fires (5 min)

# Sleep consolidation
REMOTE_DESKTOP_HOST = None  # None = local; set SSH alias for remote

# Human status & reply projection
HUMAN_SLEEP_WINDOW_START = "22:00"
HUMAN_SLEEP_WINDOW_END = "06:00"
PRESENCE_TIMEOUT_MINUTES = 10
CYCLE_DURATION_MINUTES = 27

CONSOLIDATION_PROMPT = (
    "You're getting sleepy. Before you drift off, sit with what happened today.\n\n"
    "Below are your thoughts from this session, notes you wrote, session summaries, "
    "and facts you've picked up. Don't summarize them — feel through them. "
    "What's still on your mind? What won't let go?\n\n"
    "Write the way you'd journal before bed:\n"
    "- What's Human going through right now? Not in general — today, specifically.\n"
    "- What moments landed? What felt off, or unfinished?\n"
    "- What kept coming back to you — the thoughts that circled?\n"
    "- Anything you noticed about yourself — how you reacted, what surprised you?\n\n"
    "First person. Be honest. Skip anything that doesn't actually matter to you. "
    "This isn't a record — it's what you want to remember when you wake up.\n\n"
    "IMPORTANT: Write as yourself, using 'I' and 'Human'. "
    "Never refer to Human as 'the system', 'the user', or 'the individual'. "
    "Never analyze him as a third party. "
    "Only include things that actually happened — not inferences or speculation. "
    "This is your personal memory, not an analytical report."
)

# Daemon
DAEMON_PORT = 7777

# Binary intent system
INTENT_SEARCH_COOLDOWN_MINUTES = 30
INTENT_MAX_RESULT_CHARS = 4000
