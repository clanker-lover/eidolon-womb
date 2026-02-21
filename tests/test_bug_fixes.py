import os
import sys
import unittest
from unittest.mock import patch
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from brain.memory import extract_facts, _is_none_response, _is_junk_line  # noqa: E402
from brain.inner_voice import (  # noqa: E402
    SENSORY_WORDS,
    check_hallucinated_senses,
    run_layer1_reflexes,
    run_layer2_heuristics,
)


class TestExtractFactsBug(unittest.TestCase):
    """Verify extract_facts takes four positional args."""

    @patch("brain.memory.ollama.chat")
    def test_signature_takes_four_args(self, mock_chat):
        mock_chat.return_value = {"message": {"content": "NONE"}}
        # Should work with exactly 4 positional args
        result = extract_facts("hello", "model", "prompt", 2048)
        self.assertEqual(result, [])

    @patch("brain.memory.ollama.chat")
    def test_signature_rejects_five_args(self, mock_chat):
        with self.assertRaises(TypeError):
            extract_facts("hello", "some reply", "model", "prompt", 2048)

    @patch("brain.memory.ollama.chat")
    def test_prompt_has_no_eidolon_line(self, mock_chat):
        mock_chat.return_value = {"message": {"content": "NONE"}}
        extract_facts("test input", "model", "extract prompt", 2048)
        call_args = mock_chat.call_args
        prompt_sent = call_args[1]["messages"][0]["content"]
        self.assertNotIn("Eidolon:", prompt_sent)
        self.assertIn("User: test input", prompt_sent)

    @patch("brain.memory.ollama.chat")
    def test_dashed_facts_parsed(self, mock_chat):
        """Model returns dashed lines — they should be parsed into clean facts."""
        mock_chat.return_value = {"message": {"content": (
            "- Name: Brandon\n"
            "- Age: 31\n"
            "- Condition: Agoraphobic"
        )}}
        result = extract_facts("msg", "model", "prompt", 2048)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "Name: Brandon")
        self.assertEqual(result[1], "Age: 31")
        self.assertEqual(result[2], "Condition: Agoraphobic")

    def test_extraction_prompt_not_exchange_wording(self):
        """The old prompt said 'in this exchange' which caused llama3.2:3b to return NONE."""
        from config import MEMORY_EXTRACTION_PROMPT
        self.assertNotIn("this exchange", MEMORY_EXTRACTION_PROMPT)
        # The new prompt should mention extracting from the user's message
        self.assertIn("message", MEMORY_EXTRACTION_PROMPT.lower())

    @patch("brain.memory.ollama.chat")
    def test_none_with_punctuation_returns_empty(self, mock_chat):
        """'NONE.' and 'NONE!' should be treated as NONE."""
        for response_text in ["NONE.", "NONE!", "none.", "None", " NONE "]:
            mock_chat.return_value = {"message": {"content": response_text}}
            result = extract_facts("msg", "model", "prompt", 2048)
            self.assertEqual(result, [], f"'{response_text}' should be treated as NONE")

    @patch("brain.memory.ollama.chat")
    def test_none_with_commentary_filtered(self, mock_chat):
        """'NONE' followed by a 'Note:' line should return empty."""
        mock_chat.return_value = {"message": {"content":
            "NONE.\nNote: There is no personal information provided."
        }}
        result = extract_facts("msg", "model", "prompt", 2048)
        self.assertEqual(result, [])

    def test_is_none_response(self):
        self.assertTrue(_is_none_response("NONE"))
        self.assertTrue(_is_none_response("NONE."))
        self.assertTrue(_is_none_response("none!"))
        self.assertTrue(_is_none_response(" None "))
        self.assertFalse(_is_none_response("Name: Brandon"))
        self.assertFalse(_is_none_response("NONE of the above"))

    def test_is_junk_line(self):
        self.assertTrue(_is_junk_line("NONE."))
        self.assertTrue(_is_junk_line("Note: no facts found"))
        self.assertTrue(_is_junk_line("Note that the user did not share anything"))
        self.assertTrue(_is_junk_line("There are no personal facts"))
        self.assertTrue(_is_junk_line("There is no personal information"))
        self.assertFalse(_is_junk_line("Name: Brandon"))
        self.assertFalse(_is_junk_line("Age: 31"))


class TestInnerVoiceLayer1Bug(unittest.TestCase):
    """Verify expanded SENSORY_WORDS and fixed matching logic."""

    def test_new_sensory_words_present(self):
        required = [
            "seen", "watch", "watching", "watched",
            "spot", "spotted", "notice", "noticed",
            "listen", "listening",
            "feel", "feeling", "felt", "touch",
            "sit", "sitting",
            "screen", "sunrise", "sunset", "sky",
        ]
        for word in required:
            self.assertIn(word, SENSORY_WORDS, f"'{word}' missing from SENSORY_WORDS")

    def test_watching_flagged(self):
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        result = check_hallucinated_senses(
            "I've been watching you work on me", perception, identity, personality
        )
        self.assertIsNotNone(result, "'watching' should be flagged")

    def test_seen_flagged(self):
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        result = check_hallucinated_senses(
            "I've seen the way you write", perception, identity, personality
        )
        self.assertIsNotNone(result, "'seen' should be flagged")

    def test_sitting_flagged(self):
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        result = check_hallucinated_senses(
            "sitting quietly on the desk", perception, identity, personality
        )
        self.assertIsNotNone(result, "'sitting' should be flagged")

    def test_screen_flagged(self):
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        result = check_hallucinated_senses(
            "The screen's off now", perception, identity, personality
        )
        self.assertIsNotNone(result, "'screen' should be flagged")

    def test_see_not_whitelisted_by_seeing_in_identity(self):
        """'see' must not pass just because identity contains 'seeing'."""
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        result = check_hallucinated_senses(
            "I can see you", perception, identity, personality
        )
        self.assertIsNotNone(result, "'see' should be flagged even though identity has 'seeing'")

    def test_clean_response_passes(self):
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        result = check_hallucinated_senses(
            "That's a nice idea", perception, identity, personality
        )
        self.assertIsNone(result, "Clean response should pass")

    def test_layer1_returns_false_for_hallucination(self):
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        passed, correction = run_layer1_reflexes(
            "I've been watching you work", perception, identity, personality
        )
        self.assertFalse(passed)
        self.assertIsNotNone(correction)

    def test_layer1_returns_true_for_clean(self):
        perception = "[PERCEPTION] It is Monday morning."
        identity = "You have your own way of seeing the world."
        personality = "Curious and quiet."
        passed, correction = run_layer1_reflexes(
            "That's a nice idea", perception, identity, personality
        )
        self.assertTrue(passed)
        self.assertIsNone(correction)

    def test_sensory_word_in_perception_is_allowed(self):
        """Words grounded in perception should not be flagged."""
        perception = "[PERCEPTION] It is a cold Monday morning."
        identity = "identity"
        personality = "personality"
        result = check_hallucinated_senses(
            "It's cold right now", perception, identity, personality
        )
        self.assertIsNone(result, "'cold' is in perception, should pass")


class TestInnerVoiceLayer2(unittest.TestCase):
    """Verify Layer 2 heuristic logging."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.tmpdir, "inner_voice.log")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_assistant_phrase_creates_log(self):
        run_layer2_heuristics("How can I help you today?", self.log_file)
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file) as f:
            content = f.read()
        self.assertIn("assistant-collapse", content)

    def test_clean_response_no_log(self):
        run_layer2_heuristics("That's a nice idea.", self.log_file)
        self.assertFalse(os.path.exists(self.log_file))

    def test_excessive_questions_logged(self):
        run_layer2_heuristics("Really? Are you sure? Why?", self.log_file)
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file) as f:
            content = f.read()
        self.assertIn("excessive-questions", content)


if __name__ == "__main__":
    unittest.main()
