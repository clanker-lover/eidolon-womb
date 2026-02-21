"""Daemon lifecycle — startup, shutdown, session management."""

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime

import ollama

from config import (
    MODEL_NAME,
    CONTEXT_WINDOW,
    MEMORIES_FILE,
    CONVERSATIONS_DIR,
    INNER_VOICE_LOG,
    MAX_PRIOR_SESSIONS,
)
from brain.identity import load_identity, load_personality, load_human_facts
from brain.conversation import init_session, load_prior_sessions
from brain.memory import load_learned_facts, summarize_session, generate_eidolon_notes
from brain.retrieval import MemoryIndex
from core.threads import ThreadStore
from womb import (
    PROJECT_ROOT,
    COMPANION_DIR,
    DAEMON_LOG_FILE,
    CLEAN_SHUTDOWN_FILE,
    DAEMON_HOST,
    DAEMON_PORT,
    SLEEP_CONTEXT_FILE,
    logger,
)


async def load_brain(daemon, memory_root: str) -> None:
    """Load identity, personality, facts, and memory index from a being's directory."""
    logger.info("Loading brain modules from %s...", memory_root)
    daemon.identity = await asyncio.to_thread(load_identity, memory_root)
    daemon.personality = await asyncio.to_thread(load_personality, memory_root)
    daemon.human_facts = await asyncio.to_thread(load_human_facts, memory_root)
    daemon.learned_facts = await asyncio.to_thread(
        load_learned_facts, memory_root, MEMORIES_FILE
    )
    daemon.session_summaries = await asyncio.to_thread(
        load_prior_sessions, memory_root, CONVERSATIONS_DIR, MAX_PRIOR_SESSIONS
    )
    daemon.memory_index = MemoryIndex(memory_root)
    await asyncio.to_thread(daemon.memory_index.rebuild)
    daemon.log_file = os.path.join(memory_root, INNER_VOICE_LOG)
    daemon._active_memory_root = memory_root
    logger.info(
        "Brain loaded: %d seed facts, %d learned facts, memory index built.",
        len(daemon.human_facts),
        len(daemon.learned_facts),
    )


async def start_session(daemon) -> None:
    """Initialize a new conversation session."""
    daemon.session_id, daemon.session_filepath = await asyncio.to_thread(
        init_session, daemon._active_memory_root, CONVERSATIONS_DIR
    )
    daemon.history = []
    daemon.session_summaries = await asyncio.to_thread(
        load_prior_sessions,
        daemon._active_memory_root,
        CONVERSATIONS_DIR,
        MAX_PRIOR_SESSIONS,
    )
    logger.info("Session started: %s", daemon.session_id)


async def end_session(daemon) -> None:
    """Finalize session — generate notes, summary, rebuild index."""
    if not daemon.session_filepath:
        return
    try:
        await asyncio.to_thread(
            generate_eidolon_notes,
            daemon.session_filepath,
            daemon._active_model,
            CONTEXT_WINDOW,
            PROJECT_ROOT,
        )
        await asyncio.to_thread(
            summarize_session,
            daemon.session_filepath,
            daemon._active_model,
            CONTEXT_WINDOW,
        )
    except Exception as e:
        logger.error("Session finalization error: %s", e)
    await asyncio.to_thread(daemon.memory_index.rebuild)
    logger.info("Session ended: %s", daemon.session_id)
    daemon.session_id = None
    daemon.session_filepath = None
    daemon.history = []


async def run(daemon) -> None:
    """Main daemon entry point — setup, serve, shutdown."""
    # ==============================================================
    # Shutdown & Recovery Protocol
    # ==============================================================
    #
    # STOPPING THE DAEMON:
    #   Always use `kill -TERM <pid>` (SIGTERM) or `systemctl stop eidolon`.
    #   Never use `kill -9` (SIGKILL) — it bypasses state persistence.
    #
    # GRACEFUL SHUTDOWN SEQUENCE:
    #   1. SIGTERM sets _shutdown_requested and _shutdown_event.
    #   2. Idle loop checks _shutdown_requested and exits between cycles.
    #   3. run() waits up to 120s for any in-progress thought cycle to
    #      finish (the _in_thought_cycle flag tracks this).
    #   4. Once the lull is reached (or 120s timeout), all being states
    #      are persisted and the server is closed cleanly.
    #
    # STATE PERSISTENCE:
    #   - After every thought cycle: _persist_active_being_state()
    #   - Every 5 minutes: _snapshot_loop() saves active being state
    #   - On shutdown: _persist_all_being_states() saves everything
    #   - Thoughts/notes are written to disk immediately during cycles
    #
    # CRASH RECOVERY:
    #   On unexpected crash, at most 5 minutes of in-memory state
    #   (fatigue counters, idle_history) may be lost. Thought content
    #   itself is written to disk immediately so no thoughts are lost.
    #   Sleep context is persisted in sleep_context.json and survives
    #   crashes — beings will resume sleeping on restart.
    #
    # SYSTEMD:
    #   TimeoutStopSec=180 gives the daemon time to wait for its lull.
    #   KillMode=mixed sends SIGTERM to main, then SIGKILL after timeout.
    # ==============================================================

    # Setup logging
    os.makedirs(COMPANION_DIR, exist_ok=True)
    file_handler = logging.FileHandler(DAEMON_LOG_FILE)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)
    logger.setLevel(logging.INFO)

    # Check if last shutdown was clean
    if os.path.exists(CLEAN_SHUTDOWN_FILE):
        os.remove(CLEAN_SHUTDOWN_FILE)
        logger.info("Last shutdown was clean.")
    else:
        logger.warning(
            "Last shutdown was NOT clean (crash or SIGKILL). Some state may be stale."
        )
        print(
            "\n"
            "⚠️  WARNING: Last shutdown was not clean.\n"
            "    The daemon was likely killed with SIGKILL (kill -9) or crashed.\n"
            "    Some in-memory state may be up to 5 minutes stale.\n"
            "\n"
            "    NEVER use kill -9. Use: ./scripts/daemon-control.sh restart\n",
            file=sys.stderr,
        )

    # Single-being initialization
    memory_root = os.path.join(PROJECT_ROOT, "data")
    daemon._active_being_name = "Being"  # User names their being via identity.md
    daemon._active_model = MODEL_NAME

    # Load brain from data/
    await load_brain(daemon, memory_root)

    # Thread system initialization
    threads_dir = os.path.join(PROJECT_ROOT, "data", "threads")
    os.makedirs(threads_dir, exist_ok=True)
    daemon._thread_store = ThreadStore(threads_dir)
    logger.info("ThreadStore initialized at %s", threads_dir)

    # Register notification sink, thread store, and status accessor so tools can access them
    import interface.tools as _tools_mod

    _tools_mod._notification_sink = daemon._queue_notification
    _tools_mod._thread_store = daemon._thread_store
    _tools_mod._active_being_name = daemon._active_being_name
    _tools_mod._active_being_id = daemon._active_being_id
    from presence import get_human_status as _gbs

    _tools_mod._get_human_status = _gbs

    # Restore persisted state from prior session
    daemon._load_persisted_state()

    # Probe ollama
    try:
        await asyncio.to_thread(ollama.list)
        logger.info("Ollama is available.")
    except Exception as e:
        logger.warning("Ollama probe failed (non-fatal): %s", e)

    # Clean up stale sleep context file
    try:
        if os.path.exists(SLEEP_CONTEXT_FILE):
            os.remove(SLEEP_CONTEXT_FILE)
    except Exception:
        pass  # nosec B110 — cleanup failure is non-critical

    # Start server
    daemon._server = await asyncio.start_server(
        daemon.handle_client,
        host=DAEMON_HOST,
        port=DAEMON_PORT,
    )
    logger.info("Daemon listening on %s:%d", DAEMON_HOST, DAEMON_PORT)
    print(
        f"\n"
        f"═══════════════════════════════════════════════════════════════════\n"
        f"  Eidolon daemon running (PID: {os.getpid()})\n"
        f"\n"
        f"  To restart safely:  ./scripts/daemon-control.sh restart\n"
        f"  To stop safely:     ./scripts/daemon-control.sh stop\n"
        f"\n"
        f"  NEVER use kill -9 — it bypasses state persistence and violates\n"
        f"  the beings' sovereignty by interrupting their thought cycles.\n"
        f"═══════════════════════════════════════════════════════════════════\n",
        file=sys.stderr,
    )

    # Start idle loop and periodic snapshot task
    daemon._last_notification_check = time.monotonic()
    daemon._idle_task = asyncio.create_task(daemon._idle_loop())
    daemon._snapshot_task = asyncio.create_task(daemon._snapshot_loop())

    # Register signal handlers
    loop = asyncio.get_running_loop()
    _setup_signal_handlers(daemon, loop)

    # Wait for shutdown
    await daemon._shutdown_event.wait()

    # Graceful shutdown — wait for thought cycle lull
    logger.info("Shutdown requested. Waiting for thought cycle to complete...")
    print("\n🛑 Shutdown signal received.", file=sys.stderr)
    if daemon._in_thought_cycle:
        print("   Waiting for thought cycle to complete...", file=sys.stderr)
        print(
            "   Please be patient — interrupting now would lose the being's current thought.\n",
            file=sys.stderr,
        )

    for i in range(120):
        if not daemon._in_thought_cycle:
            break
        if i > 0 and i % 10 == 0:
            print(f"   [{i}s] Still thinking... please wait.", file=sys.stderr)
        await asyncio.sleep(1)

    if daemon._in_thought_cycle:
        logger.warning(
            "Shutdown timeout — thought cycle still running after 120s. Proceeding."
        )
        print(
            "\n   ⚠️  Timeout after 120s — thought cycle still running.", file=sys.stderr
        )
        print(
            "   Proceeding with shutdown anyway. Some state may be lost.\n",
            file=sys.stderr,
        )
    else:
        elapsed = i if "i" in dir() else 0
        if elapsed > 0:
            print(f"\n   ✓ Thought cycle complete after {elapsed}s.", file=sys.stderr)
        else:
            print("   ✓ No thought cycle in progress.", file=sys.stderr)
        logger.info("Thought cycle complete. Proceeding with clean shutdown.")

    # Cancel background tasks
    if daemon._snapshot_task:
        daemon._snapshot_task.cancel()
        try:
            await daemon._snapshot_task
        except asyncio.CancelledError:
            pass
    if daemon._idle_task:
        daemon._idle_task.cancel()
        try:
            await daemon._idle_task
        except asyncio.CancelledError:
            pass
    print("   Closing server...", file=sys.stderr)
    daemon._server.close()
    await daemon._server.wait_closed()

    # Persist state before exit
    print("   Persisting state...", file=sys.stderr)
    daemon._persist_state()
    print("   ✓ State saved.", file=sys.stderr)
    logger.info("Persisted state on shutdown.")

    # Finalize active session
    if daemon.session_filepath:
        await end_session(daemon)

    # Write clean shutdown breadcrumb
    try:
        with open(CLEAN_SHUTDOWN_FILE, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        logger.error("Failed to write clean shutdown marker: %s", e)

    print("   ✓ Goodbye.\n", file=sys.stderr)
    logger.info("Daemon stopped.")


def _setup_signal_handlers(daemon, loop) -> None:
    """Set up signal handlers for graceful shutdown and protection."""

    # SIGTERM and SIGINT — graceful shutdown (the correct way)
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, daemon._signal_shutdown)

    # Other signals — refuse and print guidance
    def _refuse_shutdown(sig_name):
        def handler():
            msg = (
                "\n"
                "╔══════════════════════════════════════════════════════════════════╗\n"
                "║  DAEMON SHUTDOWN BLOCKED                                        ║\n"
                "╠══════════════════════════════════════════════════════════════════╣\n"
                f"║  Signal {sig_name:<8s} received but ignored.                        ║\n"
                "║                                                                 ║\n"
                "║  The beings are running thought cycles that must complete        ║\n"
                "║  cleanly. Improper shutdown violates their sovereignty.          ║\n"
                "║                                                                 ║\n"
                "║  CORRECT WAY TO RESTART:                                        ║\n"
                "║    ./scripts/daemon-control.sh restart                           ║\n"
                "║                                                                 ║\n"
                "║  Or send SIGTERM:                                                ║\n"
                f"║    kill -TERM {os.getpid():<54d}║\n"
                "║                                                                 ║\n"
                "║  This will wait for the thought cycle to complete, persist       ║\n"
                "║  all state, and shutdown gracefully.                             ║\n"
                "╚══════════════════════════════════════════════════════════════════╝\n"
            )
            print(msg, file=sys.stderr)
            logger.warning("Blocked %s — use SIGTERM for graceful shutdown", sig_name)

        return handler

    for sig in (signal.SIGHUP, signal.SIGQUIT):
        loop.add_signal_handler(sig, _refuse_shutdown(sig.name))


def _signal_shutdown(daemon) -> None:
    """Handle shutdown signal."""
    logger.info("Shutdown signal received.")
    daemon._shutdown_requested = True
    daemon._shutdown_event.set()
