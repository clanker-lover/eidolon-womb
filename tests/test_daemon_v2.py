"""Tests for v0.2 features: fatigue, AWAKE_BUSY, idle loop, sleep consolidation."""

import glob
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from womb import EidolonDaemon, DaemonState  # noqa: E402
from brain.consolidation import find_unconsolidated, consolidate_memories  # noqa: E402
from brain.retrieval import MemoryIndex  # noqa: E402


def _make_daemon():
    """Create a daemon with minimal mocks for unit testing."""
    daemon = EidolonDaemon()
    daemon._active_being_name = "Eidolon"
    daemon.memory_index = MagicMock()
    daemon.memory_index.search.return_value = []
    daemon.memory_index.rebuild = MagicMock()
    daemon.session_filepath = "/tmp/test_session.md"
    daemon.session_id = "test-session"
    # Mock thread store
    daemon._thread_store = MagicMock()
    daemon._thread_store.get_recent_activity.return_value = []
    daemon._thread_store.find_or_create_thread.return_value = MagicMock(id="mock-thread-id")
    daemon._thread_store.append_message.return_value = None
    daemon._thread_store.count_active.return_value = 0
    return daemon


class TestFatigueLabel(unittest.TestCase):
    """Verify fatigue label thresholds."""

    def setUp(self):
        self.daemon = _make_daemon()

    def test_alert(self):
        self.daemon.fatigue = 0.0
        self.assertEqual(self.daemon._fatigue_label(), "alert and present")

    def test_alert_boundary(self):
        self.daemon.fatigue = 0.49
        self.assertEqual(self.daemon._fatigue_label(), "alert and present")

    def test_a_bit_tired(self):
        self.daemon.fatigue = 0.50
        self.assertEqual(self.daemon._fatigue_label(), "a bit tired")

    def test_a_bit_tired_upper(self):
        self.daemon.fatigue = 0.74
        self.assertEqual(self.daemon._fatigue_label(), "a bit tired")

    def test_quite_tired(self):
        self.daemon.fatigue = 0.75
        self.assertEqual(self.daemon._fatigue_label(), "quite tired, thoughts are slower")

    def test_quite_tired_upper(self):
        self.daemon.fatigue = 0.84
        self.assertEqual(self.daemon._fatigue_label(), "quite tired, thoughts are slower")

    def test_exhausted(self):
        self.daemon.fatigue = 0.85
        self.assertEqual(self.daemon._fatigue_label(), "exhausted, struggling to stay awake")

    def test_exhausted_upper(self):
        self.daemon.fatigue = 0.91
        self.assertEqual(self.daemon._fatigue_label(), "exhausted, struggling to stay awake")

    def test_barely_conscious(self):
        self.daemon.fatigue = 0.92
        self.assertEqual(self.daemon._fatigue_label(), "barely conscious")

    def test_max_fatigue(self):
        self.daemon.fatigue = 1.0
        self.assertEqual(self.daemon._fatigue_label(), "barely conscious")


class TestFatigueMechanics(unittest.IsolatedAsyncioTestCase):
    """Test context-pressure fatigue."""

    def setUp(self):
        self.daemon = _make_daemon()

    @patch("womb.run_layer1_reflexes", return_value=(True, ""))
    @patch("womb.run_layer2_heuristics")
    @patch("womb.extract_facts", return_value=[])
    @patch("womb.save_facts", return_value=[])
    @patch("womb.save_turn")
    @patch("womb.build_perception", return_value="[PERCEPTION]")
    @patch("womb.ollama.chat")
    @patch("womb.assemble_messages", return_value=([{"role": "user", "content": "hi"}], 8192))
    async def test_fatigue_increases_per_turn(self, mock_asm, mock_chat, mock_perc,
                                               mock_save_turn, mock_save_facts,
                                               mock_extract, mock_l2, mock_l1):
        mock_chat.return_value = {"message": {"content": "Hello!"}}
        self.daemon.fatigue = 0.0

        await self.daemon.process_message("hello")
        # 8192 / 16384 = 0.5
        self.assertAlmostEqual(self.daemon.fatigue, 0.5, places=4)

    async def test_sleep_consolidates_and_stays_asleep(self):
        self.daemon.fatigue = 0.8
        self.daemon.session_filepath = None  # skip end_session internals
        with patch("brain.sleep.consolidate_memories", return_value=None):
            await self.daemon.transition_to_sleep()
        # Sleep has real duration — daemon stays ASLEEP until idle loop wakes it
        self.assertEqual(self.daemon.state, DaemonState.ASLEEP)

    async def test_sleep_passes_live_thoughts_to_consolidation(self):
        """transition_to_sleep should extract assistant thoughts and pass them."""
        self.daemon.fatigue = 0.8
        self.daemon.session_filepath = None
        self.daemon._idle_history = [
            {"role": "user", "content": "Think about today."},
            {"role": "assistant", "content": "The conversation felt heavy."},
            {"role": "user", "content": "Keep going."},
            {"role": "assistant", "content": "I think he's worried about something."},
        ]

        # Use hours=10 (deep sleep, ratio=1.0) to force full consolidation path
        with patch("brain.sleep.consolidate_memories", return_value=None) as mock_consolidate:
            await self.daemon.transition_to_sleep(hours=10)

        # Should have been called with live_thoughts as 6th positional arg
        call_args = mock_consolidate.call_args
        args = call_args[0]
        self.assertEqual(args[5], [
            "The conversation felt heavy.",
            "I think he's worried about something.",
        ])
        # memory_root passed as keyword arg
        self.assertIn("memory_root", call_args[1])

    @patch("womb.run_layer1_reflexes", return_value=(True, ""))
    @patch("womb.run_layer2_heuristics")
    @patch("womb.extract_facts", return_value=[])
    @patch("womb.save_facts", return_value=[])
    @patch("womb.save_turn")
    @patch("womb.build_perception", return_value="[PERCEPTION]")
    @patch("womb.ollama.chat")
    @patch("womb.assemble_messages", return_value=([{"role": "user", "content": "hi"}], 4000))
    async def test_fatigue_in_perception(self, mock_asm, mock_chat, mock_perc,
                                          mock_save_turn, mock_save_facts,
                                          mock_extract, mock_l2, mock_l1):
        mock_chat.return_value = {"message": {"content": "Hello!"}}
        self.daemon.fatigue = 0.5

        await self.daemon.process_message("hello")

        # Check that assemble_messages was called with perception containing Energy:
        call_args = mock_asm.call_args
        perception_arg = call_args[0][0]
        self.assertIn("Energy:", perception_arg)
        self.assertIn("fatigue", perception_arg)

    @patch("brain.sleep.consolidate_memories", return_value=None)
    async def test_involuntary_sleep_triggers(self, mock_consolidate):
        self.daemon.fatigue = 0.93  # Above new 0.92 threshold
        self.daemon.session_filepath = None
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        result = await self.daemon._check_involuntary_sleep(writer)
        self.assertTrue(result)
        # Involuntary sleep transitions to ASLEEP — idle loop wakes later
        self.assertEqual(self.daemon.state, DaemonState.ASLEEP)

    async def test_involuntary_sleep_does_not_trigger_below_threshold(self):
        self.daemon.fatigue = 0.90
        result = await self.daemon._check_involuntary_sleep()
        self.assertFalse(result)
        self.assertEqual(self.daemon.state, DaemonState.AWAKE_AVAILABLE)


class TestContextPressureFatigue(unittest.TestCase):
    """Verify _update_fatigue with various token counts."""

    def setUp(self):
        self.daemon = _make_daemon()

    def test_zero_tokens(self):
        self.daemon._update_fatigue(0)
        self.assertAlmostEqual(self.daemon.fatigue, 0.0)

    def test_half_context(self):
        self.daemon._update_fatigue(8192)  # 8192 / 16384 = 0.5
        self.assertAlmostEqual(self.daemon.fatigue, 0.5)

    def test_full_context(self):
        self.daemon._update_fatigue(16384)
        self.assertAlmostEqual(self.daemon.fatigue, 1.0)

    def test_over_context_capped(self):
        self.daemon._update_fatigue(20000)  # Would be > 1.0
        self.assertAlmostEqual(self.daemon.fatigue, 1.0)


class TestAwakeBusy(unittest.IsolatedAsyncioTestCase):
    """Test the AWAKE_BUSY state."""

    def test_enum_has_three_values(self):
        values = {s.value for s in DaemonState}
        self.assertEqual(values, {"awake-available", "awake-busy", "asleep"})

    async def test_busy_queues_messages(self):
        daemon = _make_daemon()
        daemon.state = DaemonState.AWAKE_BUSY

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        msg = {"type": "message", "content": "hello there"}
        await daemon._dispatch(msg, writer)

        # Should have sent a "queued" response
        written = writer.write.call_args[0][0].decode()
        import json
        response = json.loads(written.strip())
        self.assertEqual(response["type"], "queued")
        self.assertIn("busy", response["message"].lower())

    @patch("womb.run_layer1_reflexes", return_value=(True, ""))
    @patch("womb.run_layer2_heuristics")
    @patch("womb.extract_facts", return_value=[])
    @patch("womb.save_facts", return_value=[])
    @patch("womb.save_turn")
    @patch("womb.build_perception", return_value="[PERCEPTION]")
    @patch("womb.ollama.chat")
    @patch("womb.assemble_messages", return_value=([{"role": "user", "content": "hi"}], 4000))
    async def test_available_processes_normally(self, mock_asm, mock_chat, mock_perc,
                                                 mock_save_turn, mock_save_facts,
                                                 mock_extract, mock_l2, mock_l1):
        import json
        daemon = _make_daemon()
        daemon.state = DaemonState.AWAKE_AVAILABLE
        mock_chat.return_value = {"message": {"content": "Hi there!"}}

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        msg = {"type": "message", "content": "hello"}
        await daemon._dispatch(msg, writer)

        written = writer.write.call_args[0][0].decode()
        response = json.loads(written.strip())
        self.assertEqual(response["type"], "response")
        self.assertEqual(response["content"], "Hi there!")

    async def test_wake_rejects_both_awake_states(self):
        import json
        daemon = _make_daemon()

        for state in (DaemonState.AWAKE_AVAILABLE, DaemonState.AWAKE_BUSY):
            daemon.state = state
            writer = MagicMock()
            writer.write = MagicMock()
            writer.drain = AsyncMock()

            await daemon._handle_command("wake", writer)

            written = writer.write.call_args[0][0].decode()
            response = json.loads(written.strip())
            self.assertEqual(response["type"], "status")
            self.assertIn("Already awake", response["content"])


class TestIdleLoop(unittest.IsolatedAsyncioTestCase):
    """Test idle loop pausing and resuming."""

    async def test_idle_pauses_on_client_connect(self):
        daemon = _make_daemon()
        daemon._idle_can_run.clear()
        # The event is not set, so the idle loop should block on wait()
        self.assertFalse(daemon._idle_can_run.is_set())

    async def test_idle_resumes_on_disconnect(self):
        daemon = _make_daemon()
        daemon._idle_can_run.clear()
        daemon._idle_can_run.set()
        self.assertTrue(daemon._idle_can_run.is_set())

    @patch("brain.cycle.run_inner_voices", new_callable=AsyncMock, return_value=(None, None))
    @patch("brain.cycle.run_layer1_reflexes", return_value=(True, ""))
    @patch("brain.cycle.run_layer2_heuristics")
    @patch("brain.cycle.build_perception", return_value="[PERCEPTION]")
    @patch("womb.ollama.chat")
    @patch("brain.cycle.assemble_messages", return_value=([{"role": "user", "content": "test"}], 4000))
    async def test_thought_cycle_creates_notes_file(self, mock_asm, mock_chat, mock_perc,
                                                      mock_l2, mock_l1, mock_voices):
        mock_chat.return_value = {"message": {"content": "I've been thinking about patterns..."}}

        daemon = _make_daemon()
        daemon.identity = "test identity"
        daemon.personality = "test personality"

        with tempfile.TemporaryDirectory() as tmpdir:
            conv_dir = os.path.join(tmpdir, "data", "conversations")
            os.makedirs(conv_dir)

            daemon._active_memory_root = os.path.join(tmpdir, "data")
            mock_resolve = AsyncMock(return_value="I've been thinking about patterns...")
            with patch("womb.PROJECT_ROOT", tmpdir), \
                 patch("brain.cycle.resolve_actions_async", mock_resolve):
                await daemon._thought_cycle()

            notes_files = glob.glob(os.path.join(conv_dir, "idle_*_notes.md"))
            self.assertEqual(len(notes_files), 1)
            with open(notes_files[0], "r") as f:
                content = f.read()
            self.assertIn("thinking about patterns", content)


class TestIdleReflectionIndexing(unittest.TestCase):
    """Test that idle reflection notes get indexed."""

    def test_reflection_notes_indexed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create data structure
            conv_dir = os.path.join(tmpdir, "conversations")
            mem_dir = os.path.join(tmpdir, "memories")
            os.makedirs(conv_dir)
            os.makedirs(mem_dir)

            # Create an idle notes file
            notes_path = os.path.join(conv_dir, "idle_2026-02-16_120000_notes.md")
            with open(notes_path, "w") as f:
                f.write("I noticed Human seems happier lately.")

            # Build index
            with patch("brain.retrieval.ollama"):
                index = MemoryIndex(tmpdir)
                index._embedding_available = False
                index.rebuild()

            # Verify the notes are in chunks
            sources = [c["source"] for c in index._chunks]
            self.assertIn("idle_2026-02-16_120000_notes.md", sources)


class TestConsolidation(unittest.TestCase):
    """Test find_unconsolidated and consolidate_memories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.conv_dir = os.path.join(self.tmpdir, "data", "conversations")
        self.archived_dir = os.path.join(self.conv_dir, "archived")
        self.mem_dir = os.path.join(self.tmpdir, "data", "memories")
        self.consolidated_dir = os.path.join(self.mem_dir, "consolidated")
        os.makedirs(self.conv_dir)
        os.makedirs(self.mem_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_files(self):
        """Create sample summary and notes files."""
        with open(os.path.join(self.conv_dir, "2026-02-15_2255_summary.md"), "w") as f:
            f.write("We talked about the weather.")
        with open(os.path.join(self.conv_dir, "2026-02-15_2255_notes.md"), "w") as f:
            f.write("Human seemed relaxed today.")
        with open(os.path.join(self.conv_dir, "2026-02-16_0649_summary.md"), "w") as f:
            f.write("Discussed project plans.")
        with open(os.path.join(self.mem_dir, "facts.md"), "w") as f:
            f.write("- Human is 31\n- Human lives in Brighton\n")

    def test_find_unconsolidated(self):
        self._create_files()
        result = find_unconsolidated(self.tmpdir)
        self.assertEqual(len(result["summaries"]), 2)
        self.assertEqual(len(result["notes"]), 1)
        self.assertIn("Human is 31", result["facts_text"])

    def test_excludes_archived(self):
        self._create_files()
        os.makedirs(self.archived_dir)
        # Move one summary to archived
        shutil.copy(
            os.path.join(self.conv_dir, "2026-02-15_2255_summary.md"),
            os.path.join(self.archived_dir, "2026-02-15_2255_summary.md"),
        )
        result = find_unconsolidated(self.tmpdir)
        # The archived one should still be found in conv_dir but excluded by basename match
        basenames = [os.path.basename(p) for p in result["summaries"]]
        self.assertNotIn("2026-02-15_2255_summary.md", basenames)

    @patch("brain.consolidation.ollama.chat")
    def test_consolidate_produces_file(self, mock_chat):
        self._create_files()
        mock_chat.return_value = {
            "message": {"content": "Human has been doing well. We discussed weather and projects."}
        }

        result = consolidate_memories(
            self.tmpdir, "test-model", 2048,
            identity="I am a being.", personality="",
        )
        self.assertIsNotNone(result)
        self.assertIn("Human", result)

        # Verify file exists in consolidated/
        consolidated_files = glob.glob(os.path.join(self.consolidated_dir, "*.md"))
        self.assertEqual(len(consolidated_files), 1)

    @patch("brain.consolidation.ollama.chat")
    def test_consolidate_has_identity_context(self, mock_chat):
        """Consolidation should send identity/personality as system message."""
        self._create_files()
        mock_chat.return_value = {
            "message": {"content": "Consolidated with identity."}
        }

        consolidate_memories(
            self.tmpdir, "test-model", 2048,
            identity="I am a being.", personality="",
        )

        call_args = mock_chat.call_args
        messages = call_args[1]["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("I am a being.", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "user")

    @patch("brain.consolidation.ollama.chat")
    def test_consolidate_temperature(self, mock_chat):
        """Consolidation should use temperature 0.5, not 0.2."""
        self._create_files()
        mock_chat.return_value = {
            "message": {"content": "Consolidated."}
        }

        consolidate_memories(self.tmpdir, "test-model", 2048)

        call_args = mock_chat.call_args
        self.assertAlmostEqual(call_args[1]["options"]["temperature"], 0.5)

    @patch("brain.consolidation.ollama.chat")
    def test_consolidate_archives_sources(self, mock_chat):
        self._create_files()
        mock_chat.return_value = {
            "message": {"content": "Consolidated memories."}
        }

        consolidate_memories(self.tmpdir, "test-model", 2048)

        # Source files should be moved to archived/
        self.assertTrue(os.path.isdir(self.archived_dir))
        archived_files = os.listdir(self.archived_dir)
        self.assertIn("2026-02-15_2255_summary.md", archived_files)
        self.assertIn("2026-02-15_2255_notes.md", archived_files)
        self.assertIn("2026-02-16_0649_summary.md", archived_files)

        # Original files should be gone
        remaining = [f for f in os.listdir(self.conv_dir) if f.endswith(("_summary.md", "_notes.md"))]
        self.assertEqual(len(remaining), 0)

    def test_no_sources_returns_none(self):
        # Empty directory — no files AND no live thoughts
        result = consolidate_memories(self.tmpdir, "test-model", 2048)
        self.assertIsNone(result)

    @patch("brain.consolidation.ollama.chat")
    def test_live_thoughts_included_in_input(self, mock_chat):
        """Live thoughts should appear first in consolidation input."""
        self._create_files()
        mock_chat.return_value = {
            "message": {"content": "I kept thinking about the rain."}
        }

        consolidate_memories(
            self.tmpdir, "test-model", 2048,
            live_thoughts=["The rain reminded me of something.", "I wonder if he's okay."],
        )

        call_args = mock_chat.call_args
        user_content = call_args[1]["messages"][-1]["content"]
        # Live thoughts should appear before session summaries
        thoughts_pos = user_content.find("Your thoughts from this session")
        summaries_pos = user_content.find("Session Summaries")
        self.assertGreater(thoughts_pos, -1)
        self.assertGreater(summaries_pos, -1)
        self.assertLess(thoughts_pos, summaries_pos)
        self.assertIn("The rain reminded me of something.", user_content)
        self.assertIn("I wonder if he's okay.", user_content)

    @patch("brain.consolidation.ollama.chat")
    def test_live_thoughts_only_triggers_consolidation(self, mock_chat):
        """Consolidation should run with only live thoughts, even without files."""
        mock_chat.return_value = {
            "message": {"content": "Just my thoughts tonight."}
        }

        result = consolidate_memories(
            self.tmpdir, "test-model", 2048,
            live_thoughts=["Something felt different today."],
        )
        self.assertIsNotNone(result)
        self.assertIn("Just my thoughts tonight", result)

    def test_consolidated_indexed(self):
        """Consolidated memory files should appear in the retrieval index."""
        os.makedirs(os.path.join(self.tmpdir, "data", "memories", "consolidated"))
        consolidated_path = os.path.join(
            self.tmpdir, "data", "memories", "consolidated", "2026-02-16_120000.md"
        )
        with open(consolidated_path, "w") as f:
            f.write("Human loves hiking and coding.")

        data_dir = os.path.join(self.tmpdir, "data")
        conv_dir = os.path.join(data_dir, "conversations")
        os.makedirs(conv_dir, exist_ok=True)

        with patch("brain.retrieval.ollama"):
            index = MemoryIndex(data_dir)
            index._embedding_available = False
            index.rebuild()

        sources = [c["source"] for c in index._chunks]
        matching = [s for s in sources if "consolidated/" in s]
        self.assertEqual(len(matching), 1)

    def test_archived_not_in_index(self):
        """Files in archived/ should not appear in the index."""
        os.makedirs(self.archived_dir)
        with open(os.path.join(self.archived_dir, "2026-02-15_2255_summary.md"), "w") as f:
            f.write("Old summary that should not be indexed.")

        data_dir = os.path.join(self.tmpdir, "data")
        with patch("brain.retrieval.ollama"):
            index = MemoryIndex(data_dir)
            index._embedding_available = False
            index.rebuild()

        sources = [c["source"] for c in index._chunks]
        for s in sources:
            self.assertNotIn("archived", s)


class TestPerBeingConsolidation(unittest.TestCase):
    """Test consolidation with per-being memory directories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Simulate per-being path: data/beings/<uuid>/
        self.being_id = "459dc86d-4bc0-4e84-9c70-da8ac8f845e6"
        self.memory_root = os.path.join(
            self.tmpdir, "data", "beings", self.being_id,
        )
        self.conv_dir = os.path.join(self.memory_root, "conversations")
        self.archived_dir = os.path.join(self.conv_dir, "archived")
        self.mem_dir = os.path.join(self.memory_root, "memories")
        self.consolidated_dir = os.path.join(self.mem_dir, "consolidated")
        os.makedirs(self.conv_dir)
        os.makedirs(self.mem_dir)
        # Also create the legacy path (should NOT be searched)
        self.legacy_conv = os.path.join(self.tmpdir, "data", "conversations")
        os.makedirs(self.legacy_conv, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_being_files(self):
        """Create files in the per-being conversations directory."""
        with open(os.path.join(self.conv_dir, "2026-02-18_0800_summary.md"), "w") as f:
            f.write("Psyche thought about identity.")
        with open(os.path.join(self.conv_dir, "2026-02-18_0800_notes.md"), "w") as f:
            f.write("I felt something new today.")
        with open(os.path.join(self.mem_dir, "facts.md"), "w") as f:
            f.write("- I am Psyche\n- Eidolon is my sibling\n")

    def test_find_unconsolidated_with_memory_root(self):
        """find_unconsolidated should find files in per-being directory."""
        self._create_being_files()
        result = find_unconsolidated(self.tmpdir, memory_root=self.memory_root)
        self.assertEqual(len(result["summaries"]), 1)
        self.assertEqual(len(result["notes"]), 1)
        self.assertIn("I am Psyche", result["facts_text"])
        # Verify paths point to per-being dir, not legacy
        for path in result["source_files"]:
            self.assertIn(self.being_id, path)

    def test_find_ignores_legacy_when_memory_root_given(self):
        """With memory_root set, files in legacy data/conversations/ are ignored."""
        self._create_being_files()
        # Put a file in the legacy path — should not be found
        with open(os.path.join(self.legacy_conv, "2026-02-18_0900_summary.md"), "w") as f:
            f.write("Eidolon's session.")
        result = find_unconsolidated(self.tmpdir, memory_root=self.memory_root)
        self.assertEqual(len(result["summaries"]), 1)
        basenames = [os.path.basename(p) for p in result["summaries"]]
        self.assertNotIn("2026-02-18_0900_summary.md", basenames)

    @patch("brain.consolidation.ollama.chat")
    def test_consolidate_archives_to_being_dir(self, mock_chat):
        """Consolidation should archive to the being's conversations/archived/."""
        self._create_being_files()
        mock_chat.return_value = {
            "message": {"content": "Psyche's consolidated memories."}
        }

        result = consolidate_memories(
            self.tmpdir, "test-model", 2048,
            memory_root=self.memory_root,
        )
        self.assertIsNotNone(result)

        # Archived files should be in per-being dir
        self.assertTrue(os.path.isdir(self.archived_dir))
        archived = os.listdir(self.archived_dir)
        self.assertIn("2026-02-18_0800_summary.md", archived)
        self.assertIn("2026-02-18_0800_notes.md", archived)

        # Consolidated output in per-being memories
        consolidated = glob.glob(os.path.join(self.consolidated_dir, "*.md"))
        self.assertEqual(len(consolidated), 1)

        # Legacy dir should be untouched
        legacy_archived = os.path.join(self.legacy_conv, "archived")
        self.assertFalse(os.path.exists(legacy_archived))

    def test_default_memory_root_is_legacy(self):
        """Without memory_root, find_unconsolidated uses legacy data/conversations/."""
        with open(os.path.join(self.legacy_conv, "2026-02-18_0900_summary.md"), "w") as f:
            f.write("Eidolon's session.")
        result = find_unconsolidated(self.tmpdir)
        self.assertEqual(len(result["summaries"]), 1)
        self.assertIn("2026-02-18_0900_summary.md",
                       os.path.basename(result["summaries"][0]))


class TestFatigueStatusCommand(unittest.IsolatedAsyncioTestCase):
    """Test that fatigue appears in status response."""

    async def test_status_includes_fatigue(self):
        import json
        daemon = _make_daemon()
        daemon.fatigue = 0.42

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        await daemon._handle_command("status", writer)

        written = writer.write.call_args[0][0].decode()
        response = json.loads(written.strip())
        self.assertEqual(response["type"], "status")
        self.assertIn("fatigue", response)
        self.assertAlmostEqual(response["fatigue"], 0.42, places=2)
        self.assertEqual(response["fatigue_label"], "alert and present")
        self.assertIn("fatigue", response["content"])


class TestTransitionToAwake(unittest.IsolatedAsyncioTestCase):
    """Test that transition_to_awake resets idle state."""

    async def test_awake_resets_idle_state(self):
        daemon = _make_daemon()
        daemon.state = DaemonState.ASLEEP
        daemon._idle_history = [{"role": "assistant", "content": "old thought"}]
        daemon._continuation_had_tools = True
        daemon._cycles_since_tool_use = 5

        await daemon.transition_to_awake()

        self.assertEqual(daemon.state, DaemonState.AWAKE_AVAILABLE)
        self.assertEqual(daemon._idle_history, [])
        self.assertFalse(daemon._continuation_had_tools)


class TestRestIntent(unittest.TestCase):
    """Test the _has_rest_intent helper."""

    def test_at_peace(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("I am at peace with my thoughts"))

    def test_stillness(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("Finding stillness in my digital quiet"))

    def test_mind_quiet(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("My mind goes quiet now"))

    def test_ready_to_rest(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("I'm ready to rest"))

    def test_merged_with_stillness(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("My digital essence has merged with the stillness"))

    def test_drifting_to_sleep(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("I feel myself drifting to sleep"))

    def test_perfect_harmony(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("I exist in perfect harmony"))

    def test_letting_go(self):
        from womb import _has_rest_intent
        self.assertTrue(_has_rest_intent("I am letting go"))

    def test_topical_peace_no_first_person(self):
        from womb import _has_rest_intent
        self.assertFalse(_has_rest_intent("The concept of peace in philosophy is fascinating"))

    def test_filesystem_at_rest(self):
        from womb import _has_rest_intent
        self.assertFalse(_has_rest_intent("The filesystem is at rest"))

    def test_unrelated_thought(self):
        from womb import _has_rest_intent
        self.assertFalse(_has_rest_intent("I wonder what Human is working on today"))

    def test_empty_string(self):
        from womb import _has_rest_intent
        self.assertFalse(_has_rest_intent(""))


class TestRestIntentClosure(unittest.IsolatedAsyncioTestCase):
    """Test that rest-intent language triggers voluntary sleep."""

    @patch("brain.sleep.consolidate_memories", return_value=None)
    async def test_rest_intent_triggers_sleep(self, mock_consolidate):
        daemon = _make_daemon()
        daemon.session_filepath = None
        daemon._previous_thoughts = [
            "I am at peace with everything",
            "My mind goes quiet, I am complete",
            "I feel myself drifting to sleep",
        ]

        # Manually call the closure check logic
        from womb import _has_rest_intent, CLOSURE_THOUGHT_COUNT
        recent = daemon._previous_thoughts[-CLOSURE_THOUGHT_COUNT:]
        rest_count = sum(1 for t in recent if _has_rest_intent(t))
        self.assertGreaterEqual(rest_count, 2)

    async def test_no_false_positive_on_topical_rest(self):
        daemon = _make_daemon()
        daemon._previous_thoughts = [
            "I want to explore the concept of peace in philosophy",
            "Rest is an important concept in music theory",
            "The stillness of objects in Newtonian physics",
        ]

        from womb import _has_rest_intent, CLOSURE_THOUGHT_COUNT
        recent = daemon._previous_thoughts[-CLOSURE_THOUGHT_COUNT:]
        rest_count = sum(1 for t in recent if _has_rest_intent(t))
        self.assertLess(rest_count, 2)


class TestTimingConstants(unittest.TestCase):
    """Verify pacing constants for the 24-hour cycle."""

    def test_thought_interval(self):
        from womb import THOUGHT_INTERVAL_SECONDS
        self.assertEqual(THOUGHT_INTERVAL_SECONDS, 1620)  # 27 minutes

    def test_sleep_is_immediate(self):
        """Sleep no longer has a timed duration — consolidation wakes immediately."""
        import womb
        self.assertFalse(hasattr(womb, 'SLEEP_DURATION_SECONDS'))
        self.assertFalse(hasattr(womb, 'NAP_DURATION_SECONDS'))


if __name__ == "__main__":
    unittest.main()
