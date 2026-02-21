#!/usr/bin/env python3
"""Eidolon daemon — persistent asyncio process with Unix socket interface."""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import ollama  # noqa: E402 — must come after sys.path insert
from config import (  # noqa: E402
    MODEL_NAME, TEMPERATURE, CONTEXT_WINDOW, RESPONSE_RESERVE, MEMORIES_FILE,
    CONVERSATIONS_DIR,  # noqa: F401 — re-exported for test patching
    INNER_VOICE_MAX_RETRIES, MEMORY_EXTRACTION_PROMPT, RETRIEVAL_TOP_K,
    FATIGUE_TIRED, FATIGUE_VERY_TIRED, FATIGUE_EXHAUSTED,
    FATIGUE_INVOLUNTARY_SLEEP,
    NOTIFICATION_CHECK_INTERVAL, NOTIFICATION_COOLDOWN,
    HOT_VOICE_LOOKBACK_COUNT, HOT_VOICE_SIMILARITY_THRESHOLD,
    EMBEDDING_MODEL,
    DEFAULT_SLEEP_HOURS,
    CLOSURE_THOUGHT_COUNT,  # noqa: F401 — re-exported for tests
)
from core.patterns import has_rest_intent as _has_rest_intent  # noqa: E402, F401 — re-exported for tests
from presence import is_brandon_away  # noqa: E402
from tools import fire_notify_send  # noqa: E402
from brain.perception import build_perception  # noqa: E402
from brain.context import assemble_messages  # noqa: E402
from brain.conversation import save_turn  # noqa: E402
from brain.memory import (  # noqa: E402
    extract_facts, save_facts,
    load_learned_facts,  # noqa: F401 — re-exported for tests
)
from brain.retrieval import MemoryIndex  # noqa: E402
from brain.inner_voice import run_layer1_reflexes, run_layer2_heuristics  # noqa: E402
from brain.actions import resolve_actions_async  # noqa: E402
from inner_voices import should_cold_fire, run_cold_voice, run_hot_voice, cosine_similarity  # noqa: E402
from core.threads import ThreadStore  # noqa: E402
from core.stats import increment as stats_increment  # noqa: E402

# Daemon constants — kept here, not in config.py
COMPANION_DIR = os.path.expanduser("~/.companion")
SOCKET_PATH = os.path.join(COMPANION_DIR, "companion.sock")
MESSAGE_QUEUE_FILE = os.path.join(COMPANION_DIR, "message_queue.json")
DAEMON_LOG_FILE = os.path.join(COMPANION_DIR, "daemon.log")
DAEMON_HOST = "0.0.0.0"  # nosec B104 — intentional LAN access for local daemon
DAEMON_PORT = 7777
SLEEP_CONTEXT_FILE = os.path.join(COMPANION_DIR, "sleep_context.json")
CLEAN_SHUTDOWN_FILE = os.path.join(COMPANION_DIR, ".clean_shutdown")

# Pacing: thoughts spaced 27 minutes apart. Sleep = consolidation + immediate wake.
THOUGHT_INTERVAL_SECONDS = 1620   # 27 minutes between thoughts



logger = logging.getLogger("companion_daemon")


from core.queue import DaemonState, MessageQueue  # noqa: E402


def _format_sleep_memory(ctx: dict) -> str:
    from brain.sleep import format_sleep_memory
    return format_sleep_memory(ctx)


class EidolonDaemon:
    def __init__(self):
        # Persistent state (survives across client sessions)
        self.identity: str = ""
        self.personality: str = ""
        self.brandon_facts: list[str] = []
        self.learned_facts: list[str] = []
        self.memory_index: MemoryIndex | None = None
        self.state = DaemonState.AWAKE_AVAILABLE
        self.message_queue = MessageQueue(MESSAGE_QUEUE_FILE)
        self.project_root = PROJECT_ROOT
        self.log_file = ""  # Set by load_brain() from active being's memory root

        # Per-session state (reset on each client connect/disconnect)
        self.session_id: str | None = None
        self.session_filepath: str | None = None
        self.history: list[dict] = []
        self.session_summaries: list[str] = []

        # Fatigue
        self.fatigue: float = 0.0
        self._wake_time: float = time.time()
        self._sleep_time: float | None = None
        self._scheduled_wake_time: str | None = None  # ISO timestamp; persisted in sleep context

        # Idle loop
        self._idle_task: asyncio.Task | None = None
        self._idle_can_run = asyncio.Event()
        self._idle_can_run.set()
        self._idle_history: list[dict] = []
        self._continuation_had_tools: bool = False
        self._cycles_since_tool_use: int = 0
        self._previous_thoughts: list[str] = []
        self._last_voice_name: str | None = None

        # Sleep choice state
        self._choosing_sleep: bool = False
        self._choosing_sleep_involuntary: bool = False
        self._sleep_hours: int = DEFAULT_SLEEP_HOURS

        # Connection tracking
        self._current_writer: asyncio.StreamWriter | None = None
        self._server: asyncio.Server | None = None
        self._shutdown_event = asyncio.Event()
        self._shutdown_requested: bool = False
        self._in_thought_cycle: bool = False
        self._snapshot_task: asyncio.Task | None = None

        # Thought pacing (turbo mode)
        self._thought_interval: int = THOUGHT_INTERVAL_SECONDS
        self._turbo_changed = asyncio.Event()

        # Thread reply serialization
        self._thread_reply_lock = asyncio.Lock()

        # Notification lifecycle
        self.pending_notifications: list[dict[str, str]] = []
        self.notification_sent_at: float | None = None
        self.notification_seen: bool = False
        self._last_notification_check: float = 0.0
        self._last_presence_away: bool = False
        self._notified_this_cycle: bool = False

        # Thread compose state (intent detection → compose prompt → thread creation)
        self._composing_thread_to: str | None = None
        self._composing_thread_topic: str | None = None
        self._last_thread_creation_cycle: int = 0

        # Thread engagement state (receiving flow — mirrors compose flow)
        self._pending_thread_engagement: dict | None = None
        self._thread_engage_cooldown_id: str | None = None
        self._thread_engage_cooldown_cycles: int = 0

        # Thread response dedup (prevents verbatim repeat messages to same thread)
        self._thread_response_history: dict[str, list[str]] = {}

        # Binary intent system — pending search results and cooldown
        self._pending_search_result: str | None = None
        self._last_intent_search_time: float = 0.0

        # Being identity (single-being — no registry/scheduler)
        self._thread_store: ThreadStore | None = None
        self._registry = None  # No multi-being registry in womb
        self._scheduler = None  # No scheduler in womb
        self._active_model: str = MODEL_NAME
        self._active_being_id: str | None = None
        self._active_being_name: str = "Eidolon"
        self._active_memory_root: str = ""  # Set by load_brain()

        # Monitor telemetry
        self._thought_count: int = 0
        self._last_thought_text: str = ""
        self._last_transition: dict = {
            "from": "init", "to": "awake",
            "reason": "daemon start",
            "time": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Brain loading
    # ------------------------------------------------------------------

    async def load_brain(self, memory_root: str) -> None:
        from daemon.lifecycle import load_brain as _load_brain
        return await _load_brain(self, memory_root)

    # ------------------------------------------------------------------
    # Fatigue
    # ------------------------------------------------------------------

    def _update_fatigue(self, tokens_used: int) -> None:
        self.fatigue = min(1.0, tokens_used / CONTEXT_WINDOW)
        logger.debug("Context pressure: %d/%d tokens (%.0f%%)", tokens_used, CONTEXT_WINDOW, self.fatigue * 100)

    def _fatigue_label(self) -> str:
        if self.fatigue < FATIGUE_TIRED:
            return "alert and present"
        elif self.fatigue < FATIGUE_VERY_TIRED:
            return "a bit tired"
        elif self.fatigue < FATIGUE_EXHAUSTED:
            return "quite tired, thoughts are slower"
        elif self.fatigue < FATIGUE_INVOLUNTARY_SLEEP:
            return "exhausted, struggling to stay awake"
        else:
            return "barely conscious"

    async def _check_involuntary_sleep(self, writer=None) -> bool:
        """Check fatigue for involuntary sleep during chat sessions.

        During idle thought cycles, sleep choice is handled inline instead.
        Chat sessions use default duration since there's no next cycle to parse choice.
        """
        if self.fatigue < FATIGUE_INVOLUNTARY_SLEEP:
            return False
        if writer:
            await self._send(writer, {
                "type": "status",
                "state": "asleep",
                "content": "Eidolon fell asleep from exhaustion.",
            })
        await self.transition_to_sleep(voluntary=False, hours=DEFAULT_SLEEP_HOURS)
        return True

    # ------------------------------------------------------------------
    # Sleep context capture (delegated to brain/sleep.py)
    # ------------------------------------------------------------------

    def _count_voice_firings_since(self, since: float | None) -> tuple[int, int]:
        from brain.sleep import count_voice_firings_since
        return count_voice_firings_since(self, since)

    def _capture_sleep_context(self, voluntary: bool, hours: int) -> None:
        from brain.sleep import capture_sleep_context
        capture_sleep_context(self, voluntary, hours)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def generate_reply(
        self, messages: list[dict], *, num_predict: int = RESPONSE_RESERVE
    ) -> str:
        response = await asyncio.to_thread(
            ollama.chat,
            model=self._active_model,
            messages=messages,
            stream=False,
            options={
                "temperature": TEMPERATURE,
                "num_ctx": CONTEXT_WINDOW,
                "num_predict": num_predict,
            },
        )
        return response["message"]["content"]

    # ------------------------------------------------------------------
    # Full turn pipeline (ported from chat.py lines 77-131)
    # ------------------------------------------------------------------

    async def process_message(self, user_input: str) -> str:
        # 1. Perception
        perception = await asyncio.to_thread(
            build_perception, registry=self._registry, being_name=self._active_being_name,
        )
        perception += f"\n- Energy: {self._fatigue_label()} (fatigue {self.fatigue:.0%})"

        # 2. Memory retrieval
        retrieved = []
        if self.memory_index:
            retrieved = await asyncio.to_thread(
                self.memory_index.search, user_input, RETRIEVAL_TOP_K
            )

        # 3. Assemble messages (pure function, no thread needed)
        messages, tokens_used = assemble_messages(
            perception, self.identity, self.personality, self.brandon_facts,
            self.learned_facts, self.history, user_input, self.session_summaries,
            retrieved_memories=retrieved,
        )
        self._update_fatigue(tokens_used)

        # 4. Generate reply
        try:
            reply = await self.generate_reply(messages)
        except Exception as e:
            logger.error("Ollama error: %s", e)
            return f"(I couldn't think of a response — {e})"

        # 4b. Action tag resolution
        try:
            self._notified_this_cycle = False
            msg_count_before = len(messages)
            reply = await resolve_actions_async(
                reply, self.generate_reply, messages,
                already_notified_this_cycle=self._notified_this_cycle,
            )
            if len(messages) > msg_count_before and self._active_being_id:
                stats_increment(PROJECT_ROOT, self._active_being_id, "tool_use")
        except Exception as e:
            logger.error("Action resolution error: %s", e)

        # 5. Layer 1: reflex checks with retry
        for _ in range(INNER_VOICE_MAX_RETRIES):
            passed, correction = run_layer1_reflexes(
                reply, perception, self.identity, self.personality
            )
            if passed:
                break
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": correction})
            try:
                reply = await self.generate_reply(messages)
            except Exception as e:
                logger.error("Ollama retry error: %s", e)
                break

        # 6. Layer 2: heuristic logging (never blocks)
        run_layer2_heuristics(reply, self.log_file)

        # 6b. Cold voice check on chat response
        try:
            retrieved_texts = [m["text"] if isinstance(m, dict) else m for m in retrieved]
            if should_cold_fire(reply, perception, retrieved_texts, being_name=self._active_being_name):
                cold_output = await asyncio.to_thread(
                    run_cold_voice, reply, perception, retrieved_texts
                )
                logger.info("Cold voice fired during chat: %s", cold_output[:120])
                # Regenerate with cold voice interjection prepended
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": f"A rational part of you objects: {cold_output}"})
                try:
                    reply = await self.generate_reply(messages)
                except Exception as e:
                    logger.error("Cold voice regeneration error: %s", e)
        except Exception as e:
            logger.error("Cold voice chat check error (non-blocking): %s", e)

        # 6c. Hot voice check — semantic similarity against recent assistant replies
        try:
            prior_assistant = [m["content"] for m in self.history if m["role"] == "assistant"]
            if len(prior_assistant) >= 2:
                recent = prior_assistant[-HOT_VOICE_LOOKBACK_COUNT:]
                texts = [reply] + recent
                embed_response = await asyncio.to_thread(
                    ollama.embed, model=EMBEDDING_MODEL, input=texts
                )
                vecs = embed_response["embeddings"]
                reply_vec = vecs[0]
                if any(
                    cosine_similarity(reply_vec, vecs[i + 1]) >= HOT_VOICE_SIMILARITY_THRESHOLD
                    for i in range(len(recent))
                ):
                    hot_output = await asyncio.to_thread(run_hot_voice, reply)
                    logger.info("Hot voice fired during chat: %s", hot_output[:120])
                    messages.append({"role": "assistant", "content": reply})
                    messages.append({"role": "user", "content": f"A spontaneous part of you interjects: {hot_output}"})
                    try:
                        reply = await self.generate_reply(messages)
                    except Exception as e:
                        logger.error("Hot voice regeneration error: %s", e)
        except Exception as e:
            logger.error("Hot voice chat check error (non-blocking): %s", e)

        # 7. Append to history
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": reply})

        # 8. Save turn
        try:
            if self.session_filepath:
                await asyncio.to_thread(save_turn, self.session_filepath, user_input, reply)
        except Exception as e:
            logger.error("Conversation save error: %s", e)

        # 9-11. Extract and save facts, rebuild index if needed
        try:
            new_facts = await asyncio.to_thread(
                extract_facts, user_input, self._active_model,
                MEMORY_EXTRACTION_PROMPT, CONTEXT_WINDOW,
            )
            self.learned_facts = await asyncio.to_thread(
                save_facts, self._active_memory_root, MEMORIES_FILE,
                new_facts, self.learned_facts,
            )
            if new_facts and self.memory_index:
                await asyncio.to_thread(self.memory_index.rebuild)
        except Exception as e:
            logger.error("Memory save error: %s", e)

        return reply

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def start_session(self) -> None:
        from daemon.lifecycle import start_session as _start_session
        return await _start_session(self)

    async def end_session(self) -> None:
        from daemon.lifecycle import end_session as _end_session
        return await _end_session(self)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def transition_to_sleep(self, voluntary: bool = True, hours: int = DEFAULT_SLEEP_HOURS) -> None:
        from brain.sleep import transition_to_sleep as _tts
        return await _tts(self, voluntary=voluntary, hours=hours)

    def _should_being_stay_asleep(self) -> bool:
        from brain.sleep import should_being_stay_asleep
        return should_being_stay_asleep(self)

    async def transition_to_awake(self, reason: str = "client connect") -> list[tuple[str, str, str]]:
        from brain.sleep import transition_to_awake as _tta
        return await _tta(self, reason=reason)

    # ------------------------------------------------------------------
    # Idle loop — single-being thought cycle driver
    # ------------------------------------------------------------------

    async def _idle_loop(self) -> None:
        logger.info("Idle loop started.")

        while not self._shutdown_event.is_set() and not self._shutdown_requested:
            # Gate: wait if client connected
            try:
                await self._idle_can_run.wait()
            except asyncio.CancelledError:
                break

            if self._shutdown_requested:
                break

            # Check if sleeping being should wake
            if self.state == DaemonState.ASLEEP and self._scheduled_wake_time:
                try:
                    wake_dt = datetime.fromisoformat(self._scheduled_wake_time)
                    if datetime.now() >= wake_dt:
                        await self.transition_to_awake(reason="sleep duration complete")
                except (ValueError, TypeError):
                    await self.transition_to_awake(reason="invalid wake time")

            # Skip thought cycle if asleep
            if self.state == DaemonState.ASLEEP:
                await asyncio.sleep(THOUGHT_INTERVAL_SECONDS)
                continue

            # Run thought cycle
            self.state = DaemonState.AWAKE_BUSY
            try:
                await self._thought_cycle()
            except Exception as e:
                logger.error("Thought cycle error: %s", e)
                self._idle_history = []
                self._continuation_had_tools = False
                self._cycles_since_tool_use = 0
                self._last_voice_name = None
            finally:
                if self.state == DaemonState.AWAKE_BUSY:
                    self.state = DaemonState.AWAKE_AVAILABLE

            # Check for pending shutdown between cycles
            if self._shutdown_requested:
                logger.info("Shutdown requested — exiting idle loop between cycles.")
                break

            # One presence/notification check between thoughts
            await self._check_presence_and_notifications()

            # Pace thoughts — interruptible so turbo changes take effect immediately
            self._turbo_changed.clear()
            try:
                await asyncio.wait_for(self._turbo_changed.wait(), timeout=self._thought_interval)
                logger.info("Thought pacing interrupted by turbo change.")
            except asyncio.TimeoutError:
                pass

    # ------------------------------------------------------------------
    # Snapshot loop — periodic state persistence for crash recovery
    # ------------------------------------------------------------------

    async def _snapshot_loop(self) -> None:
        SNAPSHOT_INTERVAL = 300  # 5 minutes
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(SNAPSHOT_INTERVAL)
            except asyncio.CancelledError:
                break
            if self._shutdown_requested:
                break
            self._persist_state()
            logger.debug("Periodic snapshot saved.")

    async def _thought_cycle(self) -> None:
        from brain.cycle import thought_cycle
        return await thought_cycle(self)

    async def _thought_cycle_inner(self) -> None:
        from brain.cycle import thought_cycle_inner
        return await thought_cycle_inner(self)

    async def _check_presence_and_notifications(self) -> None:
        """Check for presence changes and fire notifications. Non-blocking."""
        try:
            current_away = await asyncio.to_thread(is_brandon_away)
            if current_away != self._last_presence_away:
                logger.info("Presence changed, starting fresh thought chain.")
                self._idle_history = []
                self._continuation_had_tools = False
                self._cycles_since_tool_use = 0
                self._last_voice_name = None
            self._last_presence_away = current_away
        except Exception:
            return

        # Notification lifecycle
        if self.pending_notifications and not self.notification_seen:
            now = time.monotonic()
            if now - self._last_notification_check >= NOTIFICATION_CHECK_INTERVAL:
                self._last_notification_check = now
                try:
                    just_returned = not current_away and self._last_presence_away
                    if not current_away:
                        cooldown_ok = (
                            self.notification_sent_at is None
                            or (now - self.notification_sent_at) >= NOTIFICATION_COOLDOWN
                        )
                        if cooldown_ok or just_returned:
                            entry = self.pending_notifications.pop(0)
                            being = entry["being"]
                            msg = entry["message"]
                            await asyncio.to_thread(fire_notify_send, msg, being)
                            self.notification_sent_at = now
                except Exception as e:
                    logger.error("Notification check error: %s", e)

    @staticmethod
    def _write_file(path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)

    # ------------------------------------------------------------------
    # State persistence — single-being (inlined from colony/state.py)
    # ------------------------------------------------------------------

    _STATE_KEYS = (
        "_idle_history", "_previous_thoughts",
        "_choosing_sleep", "_choosing_sleep_involuntary",
        "fatigue", "_continuation_had_tools", "_cycles_since_tool_use",
        "_last_voice_name", "_composing_thread_to", "_composing_thread_topic",
        "_pending_thread_engagement", "_thread_engage_cooldown_id",
        "_thread_engage_cooldown_cycles", "_thought_count", "_last_thought_text",
        "_wake_time", "_sleep_time", "_scheduled_wake_time",
        "_last_thread_creation_cycle", "_thread_response_history",
        "_pending_search_result", "_last_intent_search_time",
    )

    def _state_file_path(self) -> str:
        return os.path.join(COMPANION_DIR, "being_state.json")

    def _persist_state(self) -> None:
        """Write mutable state to disk for restart recovery."""
        import copy
        state = {key: copy.deepcopy(getattr(self, key)) for key in self._STATE_KEYS}
        try:
            os.makedirs(COMPANION_DIR, exist_ok=True)
            with open(self._state_file_path(), "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error("Failed to persist state: %s", e)

    def _load_persisted_state(self) -> None:
        """Load state from disk on startup."""
        import copy
        path = self._state_file_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                state = json.load(f)
            for key, value in state.items():
                if key in self._STATE_KEYS:
                    setattr(self, key, copy.deepcopy(value))
            logger.info("Restored persisted state (fatigue=%.0f%%, thoughts=%d).",
                        self.fatigue * 100, self._thought_count)
        except Exception as e:
            logger.error("Failed to load persisted state: %s", e)

    # Legacy API — kept so callers don't break during refactor
    def _save_being_state(self, being_id: str) -> None:
        self._persist_state()

    def _restore_being_state(self, being_id: str) -> None:
        self._load_persisted_state()

    def _persist_being_state(self, being_id: str) -> None:
        self._persist_state()

    def _load_persisted_being_states(self) -> None:
        self._load_persisted_state()

    def _persist_active_being_state(self) -> None:
        self._persist_state()

    def _persist_all_being_states(self) -> None:
        self._persist_state()

    def _is_being_asleep(self, being_id: str) -> bool:
        return self.state == DaemonState.ASLEEP

    def _get_being_wake_time(self, being_id: str) -> str | None:
        return self._scheduled_wake_time

    def _wake_being_state(self, being_id: str) -> None:
        """Reset state to wake defaults."""
        self._idle_history = []
        self._previous_thoughts = []
        self._choosing_sleep = False
        self._choosing_sleep_involuntary = False
        self.fatigue = 0.0
        self._continuation_had_tools = False
        self._cycles_since_tool_use = 0
        self._last_voice_name = None
        self._composing_thread_to = None
        self._composing_thread_topic = None
        self._pending_thread_engagement = None
        self._thread_engage_cooldown_id = None
        self._thread_engage_cooldown_cycles = 0
        self._thought_count = 0
        self._last_thought_text = ""
        self._wake_time = time.time()
        self._sleep_time = None
        self._scheduled_wake_time = None
        self._last_thread_creation_cycle = 0
        self._thread_response_history = {}
        self._pending_search_result = None
        self._last_intent_search_time = 0.0
        self._persist_state()

    # ------------------------------------------------------------------
    # Thread response dedup
    # ------------------------------------------------------------------

    def _is_duplicate_thread_response(self, thread_id: str, reply: str) -> bool:
        """Check if reply is too similar to a previous response in this thread."""
        from interface.threads_handler import is_duplicate_thread_response
        return is_duplicate_thread_response(self, thread_id, reply)

    def _record_thread_response(self, thread_id: str, reply: str) -> None:
        """Record a thread response for future dedup checks."""
        from interface.threads_handler import record_thread_response
        record_thread_response(self, thread_id, reply)

    # ------------------------------------------------------------------
    # Notification lifecycle
    # ------------------------------------------------------------------

    def _queue_notification(self, message: str) -> str:
        from interface.notifications import queue_notification
        return queue_notification(self, message)

    async def _handle_peek(self, writer: asyncio.StreamWriter) -> None:
        from daemon.server import _handle_peek as _hp
        return await _hp(self, writer)

    async def _handle_turbo(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        from daemon.server import _handle_turbo as _ht
        return await _ht(self, msg, writer)

    async def _engage_thread(self, thread_id: str, user_message: str) -> str:
        """Generate a being's reply to a thread through the full thought pipeline."""
        from interface.threads_handler import engage_thread
        return await engage_thread(self, thread_id, user_message)

    async def _handle_thread_reply(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        """Handle a thread reply request — full being pipeline."""
        from interface.threads_handler import handle_thread_reply
        return await handle_thread_reply(self, msg, writer)

    # ------------------------------------------------------------------
    # Client handler
    # ------------------------------------------------------------------

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ) -> None:
        from daemon.server import handle_client as _hc
        return await _hc(self, reader, writer)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, msg: dict, writer: asyncio.StreamWriter) -> None:
        from daemon.server import _dispatch as _d
        return await _d(self, msg, writer)

    async def _handle_command(self, command: str, writer: asyncio.StreamWriter) -> None:
        from daemon.server import _handle_command as _hcmd
        return await _hcmd(self, command, writer)

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_arrival_prompt(queued: list[tuple[str, str, str]], being_id: str | None = None) -> str:
        from daemon.server import _build_arrival_prompt as _bap
        return _bap(queued, being_id=being_id)

    async def _send(self, writer: asyncio.StreamWriter, data: dict) -> None:
        from daemon.server import _send as _s
        return await _s(self, writer, data)

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    async def run(self) -> None:
        from daemon.lifecycle import run as _run
        return await _run(self)

    def _setup_signal_handlers(self, loop) -> None:
        from daemon.lifecycle import _setup_signal_handlers as _ssh
        return _ssh(self, loop)

    def _signal_shutdown(self) -> None:
        from daemon.lifecycle import _signal_shutdown as _ss
        return _ss(self)


if __name__ == "__main__":
    daemon = EidolonDaemon()
    asyncio.run(daemon.run())
