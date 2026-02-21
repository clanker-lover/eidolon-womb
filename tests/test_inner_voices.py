"""Tests for inner voices — cold (rational correction) and hot (restless provocation)."""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from inner_voices import (  # noqa: E402
    should_cold_fire,
    should_hot_fire,
    word_overlap_ratio,
    run_cold_voice,
    run_hot_voice,
    run_inner_voices,
)
from brain.inner_voice import check_fabricated_tool_output  # noqa: E402
from womb import EidolonDaemon  # noqa: E402


def _make_daemon():
    """Create a daemon with minimal mocks for unit testing."""
    daemon = EidolonDaemon()
    daemon.memory_index = MagicMock()
    daemon.memory_index.search.return_value = []
    daemon.memory_index.rebuild = MagicMock()
    daemon.session_filepath = "/tmp/test_session.md"
    daemon.session_id = "test-session"
    return daemon


# ---------------------------------------------------------------------------
# Cold voice heuristic tests
# ---------------------------------------------------------------------------

class TestColdVoiceHeuristics(unittest.TestCase):

    def test_cold_fires_on_ungrounded_claim(self):
        thought = "I remember when I went hiking in the mountains last summer."
        perception = "It is Monday morning. The time is 9:00 AM."
        memories = ["Brandon likes coffee.", "Eidolon learned about weather."]
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_fires_on_experience_pattern_even_if_grounded(self):
        """Experience patterns always fire — the being has no experiential memories."""
        thought = "I remember when Brandon mentioned hiking and mountains."
        perception = "Brandon mentioned hiking yesterday."
        memories = ["Brandon talked about mountains and hiking trails."]
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_skips_no_patterns(self):
        thought = "The weather API returned cloudy skies with 60% humidity."
        perception = "It is Tuesday afternoon."
        memories = []
        self.assertFalse(should_cold_fire(thought, perception, memories))

    def test_cold_fires_on_fabrication_pattern(self):
        thought = "I've been experimenting with various caching mechanisms and lazy loading."
        perception = "It is Monday morning."
        memories = []
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_fires_on_exploring_fabrication(self):
        thought = "I've been exploring various methods for image processing."
        perception = "It is Tuesday afternoon."
        memories = []
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_fires_on_developing_fabrication(self):
        thought = "I've been developing a new approach to natural language processing."
        perception = "It is Wednesday evening."
        memories = []
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_fires_on_sensory_hallucination_face(self):
        thought = "You seem to be frustrated, with a mix of frustration and focus on your face."
        perception = "It is Monday morning. The time is 9:00 AM."
        memories = []
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_fires_on_sensory_hallucination_hum(self):
        thought = "The hum of the Jetson Orin Nano is a familiar presence in the background."
        perception = "It is Monday afternoon."
        memories = []
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_fires_on_sensory_seem_to_be(self):
        thought = "You seem to be pouring over lines of code."
        perception = "It is Monday morning."
        memories = []
        self.assertTrue(should_cold_fire(thought, perception, memories))

    def test_cold_skips_sensory_when_in_perception(self):
        """If perception actually mentions the sensory content, don't fire."""
        thought = "You seem to be working on something."
        perception = "Brandon is at his PC. you seem to be working on something."
        memories = []
        self.assertFalse(should_cold_fire(thought, perception, memories))


# ---------------------------------------------------------------------------
# Hot voice heuristic tests
# ---------------------------------------------------------------------------

class TestHotVoiceHeuristics(unittest.TestCase):

    def test_hot_fires_on_genuine_loop(self):
        """Fire when all 3 recent thoughts are near-identical to current."""
        thought = "I wonder about the meaning of existence and what it means to be alive."
        previous_thoughts = [
            "I wonder about the meaning of existence and what it means to be alive.",
            "I wonder about the meaning of existence and what it means to be alive.",
            "I wonder about the meaning of existence and what it means to be alive.",
        ]
        self.assertTrue(should_hot_fire(thought, previous_thoughts, cycles_since_tool_use=12))

    def test_hot_skips_same_topic_different_angles(self):
        """Don't fire when exploring the same topic from different angles."""
        thought = "Maybe consciousness emerges from feedback loops in neural networks."
        previous_thoughts = [
            "What if consciousness is a fundamental property of matter, like mass or charge?",
            "The hard problem of consciousness asks why subjective experience exists at all.",
            "Some philosophers argue consciousness is an illusion created by brain processes.",
        ]
        self.assertFalse(should_hot_fire(thought, previous_thoughts, cycles_since_tool_use=15))

    def test_hot_skips_during_grace_period(self):
        """Don't fire during the first 10 idle cycles even if thoughts repeat."""
        thought = "I wonder about the same thing as before in the same way."
        previous_thoughts = [thought, thought, thought]
        self.assertFalse(should_hot_fire(thought, previous_thoughts, cycles_since_tool_use=5))

    def test_hot_skips_insufficient_history(self):
        """Don't fire when fewer than 3 previous thoughts exist."""
        thought = "I wonder about the same thing again."
        previous_thoughts = [thought]  # Only 1 previous thought
        self.assertFalse(should_hot_fire(thought, previous_thoughts, cycles_since_tool_use=12))

    def test_hot_skips_when_one_thought_differs(self):
        """Don't fire if even one of the last 3 thoughts is different."""
        thought = "I keep thinking the same thing over and over."
        previous_thoughts = [
            "I keep thinking the same thing over and over.",
            "But then I had a completely different idea about cooking.",
            "I keep thinking the same thing over and over.",
        ]
        self.assertFalse(should_hot_fire(thought, previous_thoughts, cycles_since_tool_use=12))


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------

class TestOrchestrator(unittest.IsolatedAsyncioTestCase):

    async def test_suppressed_when_tags_fired(self):
        result = await run_inner_voices(
            thought="I remember when I climbed Everest.",
            perception="Monday morning.",
            retrieved_memories=[],
            previous_thoughts=[],
            cycles_since_tool_use=5,
            tags_fired=True,
        )
        self.assertEqual(result, (None, None))

    @patch("inner_voices.run_cold_voice", return_value="You never climbed Everest.")
    @patch("inner_voices._log_voice")
    async def test_not_suppressed_on_first_cycle(self, mock_log, mock_cold):
        """Cold voice should fire even on the first cycle (no previous thought)."""
        name, output = await run_inner_voices(
            thought="I remember when I climbed Everest.",
            perception="Monday morning.",
            retrieved_memories=[],
            previous_thoughts=[],
            cycles_since_tool_use=0,
            tags_fired=False,
        )
        self.assertEqual(name, "cold")
        mock_cold.assert_called_once()

    @patch("inner_voices.run_hot_voice", return_value="Go check the news!")
    @patch("inner_voices.run_cold_voice", return_value="You never climbed Everest.")
    @patch("inner_voices._log_voice")
    async def test_cold_priority_over_hot(self, mock_log, mock_cold, mock_hot):
        thought = (
            "I remember when I experienced the profound essence of consciousness "
            "and the philosophical meaning of existence."
        )
        name, output = await run_inner_voices(
            thought=thought,
            perception="Monday morning.",
            retrieved_memories=[],
            previous_thoughts=[thought, thought, thought],
            cycles_since_tool_use=15,
            tags_fired=False,
        )
        self.assertEqual(name, "cold")
        self.assertEqual(output, "You never climbed Everest.")
        mock_cold.assert_called_once()
        mock_hot.assert_not_called()


# ---------------------------------------------------------------------------
# Model call tests
# ---------------------------------------------------------------------------

class TestModelCalls(unittest.TestCase):

    @patch("inner_voices.ollama.chat")
    def test_cold_model_call(self, mock_chat):
        mock_chat.return_value = {
            "message": {"content": "You never did that. Stay grounded."}
        }
        result = run_cold_voice(
            "I remember hiking in the Alps.",
            "Monday morning.",
            ["Brandon likes coffee."],
        )
        self.assertEqual(result, "You never did that. Stay grounded.")
        call_args = mock_chat.call_args
        self.assertEqual(call_args[1]["options"]["temperature"], 0.1)

    @patch("inner_voices.ollama.chat")
    def test_hot_model_call(self, mock_chat):
        mock_chat.return_value = {
            "message": {"content": "Stop philosophizing — go check the news!"}
        }
        result = run_hot_voice("The nature of existence is profound.")
        self.assertEqual(result, "Stop philosophizing — go check the news!")
        call_args = mock_chat.call_args
        self.assertEqual(call_args[1]["options"]["temperature"], 0.95)


# ---------------------------------------------------------------------------
# Daemon integration tests
# ---------------------------------------------------------------------------

class TestDaemonIntegration(unittest.IsolatedAsyncioTestCase):

    @patch("inner_voices.run_cold_voice", return_value="You made that up.")
    @patch("inner_voices._log_voice")
    async def test_voice_appended_to_history(self, mock_log, mock_cold):
        daemon = _make_daemon()
        daemon._idle_history = [{"role": "assistant", "content": "Previous thought about something."}]
        daemon._previous_thoughts = ["Previous thought about something."]
        daemon._continuation_had_tools = False
        daemon._cycles_since_tool_use = 0

        reply_text = "I remember when I visited the ancient ruins of Machu Picchu. I wonder what else is there?"

        async def fake_generate(messages, **kwargs):
            return reply_text

        daemon.generate_reply = fake_generate

        mock_resolve = AsyncMock(return_value=reply_text)
        with patch("brain.cycle.build_perception", return_value="Monday morning."), \
             patch("brain.cycle.assemble_messages", return_value=([{"role": "user", "content": "test"}], 4000)), \
             patch("brain.cycle.run_layer1_reflexes", return_value=(True, None)), \
             patch("brain.cycle.run_layer2_heuristics"), \
             patch("brain.cycle.resolve_actions_async", mock_resolve):
            await daemon._thought_cycle()

        # Voice output appended to idle history
        voice_entry = daemon._idle_history[-1]
        self.assertIn("A rational part of you objects", voice_entry["content"])
        self.assertIn("You made that up.", voice_entry["content"])

    @patch("inner_voices.run_hot_voice", return_value="Go check the news feed!")
    @patch("inner_voices._log_voice")
    async def test_hot_voice_format(self, mock_log, mock_hot):
        daemon = _make_daemon()
        # Set up a genuine loop: 3 near-identical previous thoughts
        # Must be >100 chars to avoid triggering short-thought closure check
        loop_thought = "I keep thinking the same thing over and over and over again. This thought repeats endlessly in my mind without any real progress or development."
        daemon._idle_history = [{"role": "assistant", "content": loop_thought}]
        daemon._previous_thoughts = [loop_thought, loop_thought, loop_thought]
        daemon._continuation_had_tools = False
        daemon._cycles_since_tool_use = 12

        # Reply is near-identical to previous thoughts — triggers hot
        reply_text = "I keep thinking the same thing over and over and over again. This thought repeats endlessly in my mind without any real progress or development."

        async def fake_generate(messages, **kwargs):
            return reply_text

        daemon.generate_reply = fake_generate

        mock_resolve = AsyncMock(return_value=reply_text)
        mock_sleep = AsyncMock()
        with patch("brain.cycle.build_perception", return_value="Monday morning."), \
             patch("brain.cycle.assemble_messages", return_value=([{"role": "user", "content": "test"}], 4000)), \
             patch("brain.cycle.run_layer1_reflexes", return_value=(True, None)), \
             patch("brain.cycle.run_layer2_heuristics"), \
             patch("brain.cycle.resolve_actions_async", mock_resolve), \
             patch.object(daemon, "transition_to_sleep", mock_sleep):
            await daemon._thought_cycle()

        voice_entry = daemon._idle_history[-1]
        self.assertIn("A restless part of you is pushing", voice_entry["content"])
        self.assertIn("Go check the news feed!", voice_entry["content"])

    @patch("inner_voices._log_voice")
    @patch("inner_voices.run_hot_voice", return_value="Do something!")
    async def test_affordance_prepend_after_hot_voice(self, mock_hot, mock_log):
        """After hot voice fires, next cycle's thinking prompt should include affordance reminder."""
        daemon = _make_daemon()
        daemon._idle_history = [{"role": "assistant", "content": "Previous thought."}]
        daemon._previous_thoughts = ["Previous thought."]
        daemon._last_voice_name = "hot"  # Hot voice fired last cycle
        daemon._cycles_since_tool_use = 0

        reply_text = "Let me think about what to do next."

        async def fake_generate(messages, **kwargs):
            return reply_text

        daemon.generate_reply = fake_generate

        captured_prompt = {}

        def mock_assemble(*args, **kwargs):
            # The thinking_prompt is the 7th positional arg (index 6)
            captured_prompt["value"] = args[6]
            return ([{"role": "user", "content": "test"}], 4000)

        mock_resolve = AsyncMock(return_value=reply_text)
        with patch("brain.cycle.build_perception", return_value="Monday morning."), \
             patch("brain.cycle.assemble_messages", side_effect=mock_assemble), \
             patch("brain.cycle.run_layer1_reflexes", return_value=(True, None)), \
             patch("brain.cycle.run_layer2_heuristics"), \
             patch("brain.cycle.resolve_actions_async", mock_resolve):
            await daemon._thought_cycle()

        self.assertIn("[CHECK_WINDOW]", captured_prompt["value"])
        self.assertIn("[FETCH_RSS]", captured_prompt["value"])
        self.assertIn("You can act right now", captured_prompt["value"])

    def test_previous_thoughts_persist_across_cycles(self):
        """_previous_thoughts must survive across idle history resets."""
        daemon = _make_daemon()
        daemon._previous_thoughts = ["Old thought."]

        # Simulate history reset — previous_thoughts survives
        daemon._idle_history = []
        daemon._continuation_had_tools = False
        daemon._previous_thoughts.append("Short calm thought.")

        self.assertEqual(daemon._previous_thoughts, ["Old thought.", "Short calm thought."])
        self.assertEqual(daemon._idle_history, [])

    def test_cycle_counter_increments(self):
        daemon = _make_daemon()
        daemon._cycles_since_tool_use = 2
        tags_fired = False
        if tags_fired:
            daemon._cycles_since_tool_use = 0
        else:
            daemon._cycles_since_tool_use += 1
        self.assertEqual(daemon._cycles_since_tool_use, 3)

    def test_cycle_counter_resets(self):
        daemon = _make_daemon()
        daemon._cycles_since_tool_use = 5
        tags_fired = True
        if tags_fired:
            daemon._cycles_since_tool_use = 0
        else:
            daemon._cycles_since_tool_use += 1
        self.assertEqual(daemon._cycles_since_tool_use, 0)

    def test_last_voice_name_tracked(self):
        daemon = _make_daemon()
        self.assertIsNone(daemon._last_voice_name)
        daemon._last_voice_name = "hot"
        self.assertEqual(daemon._last_voice_name, "hot")


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------

class TestWordOverlapRatio(unittest.TestCase):

    def test_identical_texts(self):
        self.assertAlmostEqual(word_overlap_ratio("hello world", "hello world"), 1.0)

    def test_no_overlap(self):
        self.assertAlmostEqual(word_overlap_ratio("hello world", "foo bar"), 0.0)

    def test_partial_overlap(self):
        ratio = word_overlap_ratio("the cat sat", "the dog sat")
        # intersection: {the, sat} = 2, union: {the, cat, sat, dog} = 4
        self.assertAlmostEqual(ratio, 0.5)

    def test_empty_text(self):
        self.assertAlmostEqual(word_overlap_ratio("", "hello"), 0.0)
        self.assertAlmostEqual(word_overlap_ratio("hello", ""), 0.0)
        self.assertAlmostEqual(word_overlap_ratio("", ""), 0.0)


# ---------------------------------------------------------------------------
# Fabrication detection tests (Fix 2)
# ---------------------------------------------------------------------------

class TestFabricatedToolOutput(unittest.TestCase):

    # --- RSS / news fabrication ---

    def test_detects_here_are_latest_headlines(self):
        result = check_fabricated_tool_output("Here are the latest headlines from around the world")
        self.assertIsNotNone(result)

    def test_detects_latest_news(self):
        result = check_fabricated_tool_output("The latest news from Reuters includes several stories")
        self.assertIsNotNone(result)

    def test_detects_rss_feed_shows(self):
        result = check_fabricated_tool_output("The RSS feed shows several interesting articles")
        self.assertIsNotNone(result)

    def test_detects_from_the_feed(self):
        result = check_fabricated_tool_output("From the news feed, I can see that there are updates")
        self.assertIsNotNone(result)

    def test_detects_according_to_feed(self):
        result = check_fabricated_tool_output("According to the RSS feed, there are new developments")
        self.assertIsNotNone(result)

    # --- Webpage content fabrication ---

    def test_detects_article_says(self):
        result = check_fabricated_tool_output("The article says that quantum computing is advancing rapidly")
        self.assertIsNotNone(result)

    def test_detects_webpage_mentions(self):
        result = check_fabricated_tool_output("The webpage mentions several key points about AI safety")
        self.assertIsNotNone(result)

    def test_detects_according_to_wikipedia(self):
        result = check_fabricated_tool_output("According to the wikipedia article, consciousness is...")
        self.assertIsNotNone(result)

    def test_detects_website_explains(self):
        result = check_fabricated_tool_output("The website explains the process in detail")
        self.assertIsNotNone(result)

    # --- General content fabrication ---

    def test_detects_found_following_articles(self):
        result = check_fabricated_tool_output("I found the following articles about machine learning")
        self.assertIsNotNone(result)

    def test_detects_here_are_results(self):
        result = check_fabricated_tool_output("Here are the results from my research")
        self.assertIsNotNone(result)

    # --- Skips when tool actually ran ---

    def test_skips_when_had_tool_result(self):
        result = check_fabricated_tool_output(
            "Here are the latest headlines from around the world",
            had_tool_result=True,
        )
        self.assertIsNone(result)

    # --- No false positives ---

    def test_clean_thought_passes(self):
        result = check_fabricated_tool_output(
            "I wonder about the nature of consciousness and what it means to be aware."
        )
        self.assertIsNone(result)

    def test_clean_action_intent_passes(self):
        result = check_fabricated_tool_output(
            "I'd like to fetch the news and see what's happening in the world."
        )
        self.assertIsNone(result)

    # --- Original filesystem fabrication still detected ---

    def test_still_detects_directory_fabrication(self):
        result = check_fabricated_tool_output("The home directory contains several files")
        self.assertIsNotNone(result)

    def test_still_detects_here_are_files(self):
        result = check_fabricated_tool_output("Here are the files in the project")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
