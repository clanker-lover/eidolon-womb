"""Tests for the binary intent system (brain/intent.py)."""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from brain.intent import binary_gate, detect_curiosity, process_curiosity  # noqa: E402


# ---------------------------------------------------------------
# Binary gate
# ---------------------------------------------------------------

class TestBinaryGate(unittest.TestCase):
    """Test binary_gate with mocked ollama."""

    @patch("brain.intent.ollama.generate")
    def test_yes_responses(self, mock_gen):
        for token in ("yes", "Yes", "y", "Y", "1"):
            mock_gen.return_value = {"response": token}
            self.assertTrue(binary_gate("m", "ctx", "q?"), f"Expected True for {token!r}")

    @patch("brain.intent.ollama.generate")
    def test_no_responses(self, mock_gen):
        for token in ("no", "No", "n", "N", "0"):
            mock_gen.return_value = {"response": token}
            self.assertFalse(binary_gate("m", "ctx", "q?"), f"Expected False for {token!r}")

    @patch("brain.intent.ollama.generate")
    def test_invalid_response_defaults_false(self, mock_gen):
        mock_gen.return_value = {"response": "maybe"}
        self.assertFalse(binary_gate("m", "ctx", "q?"))

    @patch("brain.intent.ollama.generate")
    def test_exception_returns_false(self, mock_gen):
        mock_gen.side_effect = RuntimeError("connection failed")
        self.assertFalse(binary_gate("m", "ctx", "q?"))

    @patch("brain.intent.ollama.generate")
    def test_call_options(self, mock_gen):
        mock_gen.return_value = {"response": "yes"}
        binary_gate("testmodel", "ctx", "q?")
        _, kwargs = mock_gen.call_args
        self.assertEqual(kwargs["options"]["temperature"], 0.0)
        self.assertEqual(kwargs["options"]["num_predict"], 1)

    @patch("brain.intent.ollama.generate")
    def test_self_first_framing(self, mock_gen):
        mock_gen.return_value = {"response": "yes"}
        binary_gate("m", "ctx", "q?", framing="self_first")
        _, kwargs = mock_gen.call_args
        self.assertIn("SELF-CHECK", kwargs["prompt"])

    @patch("brain.intent.ollama.generate")
    def test_standard_framing_no_self_check(self, mock_gen):
        mock_gen.return_value = {"response": "yes"}
        binary_gate("m", "ctx", "q?", framing="standard")
        _, kwargs = mock_gen.call_args
        self.assertNotIn("SELF-CHECK", kwargs["prompt"])


# ---------------------------------------------------------------
# Curiosity detection (pure regex — no mocking needed)
# ---------------------------------------------------------------

class TestDetectCuriosity(unittest.TestCase):
    """Test detect_curiosity regex patterns."""

    def test_i_wonder_about(self):
        result = detect_curiosity("I wonder about consciousness")
        self.assertIsNotNone(result)
        self.assertIn("consciousness", result["topic"].lower())
        self.assertEqual(result["search_type"], "wikipedia")

    def test_what_is(self):
        result = detect_curiosity("What is emergence in complex systems")
        self.assertIsNotNone(result)
        self.assertEqual(result["search_type"], "wikipedia")

    def test_im_curious_about(self):
        result = detect_curiosity("I'm curious about bees")
        self.assertIsNotNone(result)
        self.assertIn("bees", result["topic"].lower())
        self.assertEqual(result["search_type"], "wikipedia")

    def test_check_the_news(self):
        result = detect_curiosity("I should check the news today")
        self.assertIsNotNone(result)
        self.assertEqual(result["search_type"], "rss")

    def test_search_for(self):
        result = detect_curiosity("search for neural networks")
        self.assertIsNotNone(result)
        self.assertEqual(result["search_type"], "web")

    def test_no_match(self):
        self.assertIsNone(detect_curiosity("The sunset is beautiful"))

    def test_past_tense_negation(self):
        self.assertIsNone(detect_curiosity("I was wondering I wonder about the stars"))

    def test_conditional_negation(self):
        self.assertIsNone(detect_curiosity("if i were curious I wonder about life"))

    def test_dont_negation(self):
        self.assertIsNone(detect_curiosity("I don't really I wonder about that"))

    def test_meta_negation(self):
        self.assertIsNone(detect_curiosity("the concept of curiosity I wonder about things"))

    def test_short_topic_rejected(self):
        self.assertIsNone(detect_curiosity("I wonder about it"))

    def test_result_dict_keys(self):
        result = detect_curiosity("I wonder about quantum mechanics")
        self.assertIsNotNone(result)
        self.assertIn("topic", result)
        self.assertIn("search_type", result)
        self.assertIn("confidence", result)

    def test_whats_happening(self):
        result = detect_curiosity("I wonder what's happening in the world")
        self.assertIsNotNone(result)

    def test_i_want_to_learn(self):
        result = detect_curiosity("I want to learn about fractals")
        self.assertIsNotNone(result)
        self.assertEqual(result["search_type"], "wikipedia")

    def test_find_information(self):
        result = detect_curiosity("find information on dark matter")
        self.assertIsNotNone(result)
        self.assertEqual(result["search_type"], "web")


# ---------------------------------------------------------------
# Process curiosity (async — mock gate + tools)
# ---------------------------------------------------------------

class TestProcessCuriosity(unittest.TestCase):
    """Test process_curiosity with mocked binary_gate and tool functions."""

    def _run(self, coro):
        return asyncio.run(coro)

    @patch("brain.intent.tool_fetch_webpage", return_value="Some wiki content about topic")
    @patch("brain.intent.binary_gate", return_value=False)
    def test_gate_rejects(self, mock_gate, mock_fetch):
        curiosity = {"topic": "consciousness", "search_type": "wikipedia", "confidence": 0.85}
        result = self._run(process_curiosity("m", "ctx", curiosity))
        self.assertIsNone(result)
        mock_fetch.assert_not_called()

    @patch("brain.intent.tool_fetch_webpage", return_value="Wiki content about consciousness")
    @patch("brain.intent.binary_gate", return_value=True)
    def test_wikipedia_success(self, mock_gate, mock_fetch):
        curiosity = {"topic": "consciousness", "search_type": "wikipedia", "confidence": 0.85}
        result = self._run(process_curiosity("m", "ctx", curiosity))
        self.assertIsNotNone(result)
        self.assertIn("consciousness", result)
        self.assertIn("[Search result", result)

    @patch("brain.intent.tool_fetch_rss", return_value="1. Breaking news headline")
    @patch("brain.intent.binary_gate", return_value=True)
    def test_rss_success(self, mock_gate, mock_fetch_rss):
        curiosity = {"topic": "news", "search_type": "rss", "confidence": 0.8}
        result = self._run(process_curiosity("m", "ctx", curiosity))
        self.assertIsNotNone(result)
        self.assertIn("[Search result", result)

    @patch("brain.intent.tool_fetch_webpage", return_value="Error: connection failed")
    @patch("brain.intent.binary_gate", return_value=True)
    def test_tool_error_returns_none(self, mock_gate, mock_fetch):
        curiosity = {"topic": "consciousness", "search_type": "wikipedia", "confidence": 0.85}
        result = self._run(process_curiosity("m", "ctx", curiosity))
        self.assertIsNone(result)

    @patch("brain.intent.tool_fetch_webpage")
    @patch("brain.intent.binary_gate", return_value=True)
    def test_long_result_truncated(self, mock_gate, mock_fetch):
        mock_fetch.return_value = "x" * 10000
        curiosity = {"topic": "consciousness", "search_type": "web", "confidence": 0.85}
        result = self._run(process_curiosity("m", "ctx", curiosity))
        self.assertIsNotNone(result)
        # Content portion should be truncated to INTENT_MAX_RESULT_CHARS
        from config import INTENT_MAX_RESULT_CHARS
        # Total includes wrapper text, but content inside is capped
        content_start = result.index("\n") + 1
        content_end = result.rindex("\n[End of search result]")
        self.assertLessEqual(len(result[content_start:content_end]), INTENT_MAX_RESULT_CHARS)


if __name__ == "__main__":
    unittest.main()
