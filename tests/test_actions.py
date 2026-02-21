"""Tests for presence detection, tool functions, action tag parsing, and execution loop."""

import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from brain.actions import (  # noqa: E402
    parse_first_tag, strip_tags, execute_tag,
    resolve_actions_async, resolve_actions_sync,
    extract_exploration_intent, extract_notification_intent,
    extract_thread_intent, extract_dismiss_intent,
    MAX_ACTION_ROUNDS,
)
from presence import get_active_window, get_idle_seconds, get_presence_status  # noqa: E402
from tools import (  # noqa: E402
    tool_check_window, tool_list_dir, tool_read_file,
    tool_fetch_rss, tool_send_notification, TOOL_REGISTRY,
)


# ---------------------------------------------------------------
# Tag parsing
# ---------------------------------------------------------------

class TestTagParsing(unittest.TestCase):

    def test_simple_tag(self):
        result = parse_first_tag("Let me check [CHECK_WINDOW] for you")
        self.assertIsNotNone(result)
        name, arg, start, end = result
        self.assertEqual(name, "CHECK_WINDOW")
        self.assertIsNone(arg)

    def test_tag_with_argument(self):
        result = parse_first_tag("Looking at [LIST_DIR:/home/user]")
        self.assertIsNotNone(result)
        name, arg, start, end = result
        self.assertEqual(name, "LIST_DIR")
        self.assertEqual(arg, "/home/user")

    def test_no_tags(self):
        result = parse_first_tag("Just a normal response with no tags")
        self.assertIsNone(result)

    def test_lowercase_ignored(self):
        result = parse_first_tag("This has [lowercase] brackets")
        self.assertIsNone(result)

    def test_unknown_tag_skipped(self):
        result = parse_first_tag("This has [UNKNOWN_TAG] in it")
        self.assertIsNone(result)

    def test_perception_header_not_matched(self):
        # The perception header contains spaces and em-dash, won't match
        result = parse_first_tag("[PERCEPTION \u2014 Current State]")
        self.assertIsNone(result)

    def test_multiple_tags_returns_first(self):
        result = parse_first_tag("[CHECK_WINDOW] and [LIST_DIR:/tmp]")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "CHECK_WINDOW")

    def test_path_with_spaces(self):
        result = parse_first_tag("[READ_FILE:/home/user/my file.txt]")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "READ_FILE")
        self.assertEqual(result[1], "/home/user/my file.txt")

    def test_tag_at_start(self):
        result = parse_first_tag("[FETCH_RSS]")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "FETCH_RSS")

    def test_tag_positions(self):
        text = "before [CHECK_WINDOW] after"
        result = parse_first_tag(text)
        self.assertIsNotNone(result)
        name, arg, start, end = result
        self.assertEqual(text[start:end], "[CHECK_WINDOW]")


# ---------------------------------------------------------------
# Strip tags
# ---------------------------------------------------------------

class TestStripTags(unittest.TestCase):

    def test_strips_recognized(self):
        result = strip_tags("Hello [CHECK_WINDOW] world")
        self.assertEqual(result, "Hello  world")

    def test_leaves_unrecognized(self):
        result = strip_tags("Hello [UNKNOWN] world")
        self.assertEqual(result, "Hello [UNKNOWN] world")

    def test_strips_with_args(self):
        result = strip_tags("Checking [LIST_DIR:/tmp] now")
        self.assertEqual(result, "Checking  now")

    def test_noop_plain_text(self):
        text = "No tags here at all"
        self.assertEqual(strip_tags(text), text)

    def test_multiple_tags(self):
        result = strip_tags("[CHECK_WINDOW] and [FETCH_RSS]")
        self.assertEqual(result, " and ")


# ---------------------------------------------------------------
# Execute tag
# ---------------------------------------------------------------

class TestExecuteTag(unittest.TestCase):

    @patch("brain.actions.TOOL_REGISTRY", {"CHECK_WINDOW": lambda: "test result"})
    def test_execute_no_arg_tool(self):
        result = execute_tag("CHECK_WINDOW", None)
        self.assertEqual(result, "test result")

    @patch("brain.actions.TOOL_REGISTRY", {"LIST_DIR": lambda path: f"listing {path}"})
    def test_execute_with_arg(self):
        result = execute_tag("LIST_DIR", "/tmp")
        self.assertEqual(result, "listing /tmp")

    def test_unknown_tag(self):
        result = execute_tag("NONEXISTENT", None)
        self.assertIn("Unknown tool", result)

    @patch("brain.actions.TOOL_REGISTRY", {"BROKEN": MagicMock(side_effect=RuntimeError("boom"))})
    def test_exception_handling(self):
        result = execute_tag("BROKEN", None)
        self.assertIn("Error executing BROKEN", result)


# ---------------------------------------------------------------
# Resolve actions async
# ---------------------------------------------------------------

class TestResolveActionsAsync(unittest.IsolatedAsyncioTestCase):

    async def test_no_tags_passthrough(self):
        result = await resolve_actions_async("Just plain text", None, [])
        self.assertEqual(result, "Just plain text")

    async def test_single_tag_resolved(self):
        async def fake_generate(messages):
            return "The window is Firefox"

        with patch("brain.actions.execute_tag", return_value="Human is currently in: Firefox"):
            text = "Let me check [CHECK_WINDOW]"
            messages = []
            result = await resolve_actions_async(text, fake_generate, messages)
            self.assertIn("Let me check", result)
            self.assertIn("The window is Firefox", result)
            # Messages should have been extended
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]["role"], "assistant")
            self.assertIn("Tool result", messages[1]["content"])

    async def test_max_rounds_enforced(self):
        call_count = 0

        async def fake_generate(messages):
            nonlocal call_count
            call_count += 1
            return "[CHECK_WINDOW]"  # Always returns a tag

        with patch("brain.actions.execute_tag", return_value="result"):
            text = "[CHECK_WINDOW]"
            await resolve_actions_async(text, fake_generate, [])
            self.assertLessEqual(call_count, MAX_ACTION_ROUNDS)

    async def test_generation_error_handled(self):
        async def failing_generate(messages):
            raise RuntimeError("model error")

        with patch("brain.actions.execute_tag", return_value="tool output"):
            text = "[CHECK_WINDOW]"
            result = await resolve_actions_async(text, failing_generate, [])
            self.assertIn("tool output", result)


# ---------------------------------------------------------------
# Resolve actions sync
# ---------------------------------------------------------------

class TestResolveActionsSync(unittest.TestCase):

    def test_no_tags_passthrough(self):
        result = resolve_actions_sync("Plain text", None, [])
        self.assertEqual(result, "Plain text")

    def test_single_tag_resolved(self):
        def fake_generate(messages):
            return "The window is Firefox"

        with patch("brain.actions.execute_tag", return_value="Human is currently in: Firefox"):
            text = "Let me check [CHECK_WINDOW]"
            messages = []
            result = resolve_actions_sync(text, fake_generate, messages)
            self.assertIn("Let me check", result)
            self.assertIn("The window is Firefox", result)
            self.assertEqual(len(messages), 2)

    def test_max_rounds_enforced(self):
        call_count = 0

        def fake_generate(messages):
            nonlocal call_count
            call_count += 1
            return "[CHECK_WINDOW]"

        with patch("brain.actions.execute_tag", return_value="result"):
            resolve_actions_sync("[CHECK_WINDOW]", fake_generate, [])
            self.assertLessEqual(call_count, MAX_ACTION_ROUNDS)

    def test_generation_error_handled(self):
        def failing_generate(messages):
            raise RuntimeError("model error")

        with patch("brain.actions.execute_tag", return_value="tool output"):
            result = resolve_actions_sync("[CHECK_WINDOW]", failing_generate, [])
            self.assertIn("tool output", result)


# ---------------------------------------------------------------
# Presence detection
# ---------------------------------------------------------------

class TestPresenceDetection(unittest.TestCase):

    @patch("interface.presence.subprocess.run")
    def test_get_active_window_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="Firefox - Google\n")
        result = get_active_window()
        self.assertEqual(result, "Firefox - Google")

    @patch("presence.subprocess.run", side_effect=FileNotFoundError)
    def test_get_active_window_missing_tool(self, mock_run):
        result = get_active_window()
        self.assertEqual(result, "unknown")

    @patch("interface.presence.subprocess.run")
    def test_get_idle_seconds_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="5000\n")
        result = get_idle_seconds()
        self.assertAlmostEqual(result, 5.0)

    @patch("presence.subprocess.run", side_effect=FileNotFoundError)
    def test_get_idle_seconds_failure(self, mock_run):
        result = get_idle_seconds()
        self.assertEqual(result, 0.0)

    @patch("presence.get_active_window", return_value="Terminal")
    @patch("presence.get_idle_seconds", return_value=30.0)
    @patch("interface.presence.subprocess.run")
    def test_presence_active(self, mock_run, mock_idle, mock_window):
        # loginctl returns no locked sessions
        mock_run.return_value = MagicMock(stdout="1 1000 lover seat0\n")
        # The lock check
        def run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "show-session" in cmd_str:
                return MagicMock(stdout="no\n")
            return MagicMock(stdout="1 1000 lover seat0\n")
        mock_run.side_effect = run_side_effect
        result = get_presence_status()
        self.assertIn("at his PC", result)
        self.assertIn("Terminal", result)

    @patch("presence.get_active_window", return_value="Terminal")
    @patch("presence.get_idle_seconds", return_value=300.0)
    @patch("interface.presence.subprocess.run")
    def test_presence_idle(self, mock_run, mock_idle, mock_window):
        def run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "show-session" in cmd_str:
                return MagicMock(stdout="no\n")
            return MagicMock(stdout="1 1000 lover seat0\n")
        mock_run.side_effect = run_side_effect
        result = get_presence_status()
        self.assertIn("idle for 5 minutes", result)

    @patch("presence.get_active_window", return_value="unknown")
    @patch("presence.get_idle_seconds", return_value=700.0)
    @patch("interface.presence.subprocess.run")
    def test_presence_away(self, mock_run, mock_idle, mock_window):
        def run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "show-session" in cmd_str:
                return MagicMock(stdout="no\n")
            return MagicMock(stdout="1 1000 lover seat0\n")
        mock_run.side_effect = run_side_effect
        result = get_presence_status()
        self.assertIn("away from his PC", result)

    @patch("interface.presence.subprocess.run")
    def test_presence_locked(self, mock_run):
        def run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "show-session" in cmd_str:
                return MagicMock(stdout="yes\n")
            return MagicMock(stdout="1 1000 lover seat0\n")
        mock_run.side_effect = run_side_effect
        result = get_presence_status()
        self.assertIn("screen locked", result)

    @patch("presence.get_active_window", return_value="unknown")
    @patch("presence.get_idle_seconds", return_value=0.0)
    @patch("presence.subprocess.run", side_effect=FileNotFoundError)
    def test_presence_unavailable(self, mock_run, mock_idle, mock_window):
        result = get_presence_status()
        # loginctl fails, falls through to idle/window check
        self.assertIn("at his PC", result)


# ---------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------

class TestToolFunctions(unittest.TestCase):

    def test_list_dir_tmp(self):
        result = tool_list_dir("/tmp")
        self.assertIn("Contents of /tmp", result)

    def test_list_dir_missing(self):
        result = tool_list_dir("/nonexistent/path/12345")
        self.assertIn("Error", result)

    def test_list_dir_no_path(self):
        result = tool_list_dir(None)
        self.assertIn("Error", result)

    def test_read_file_missing(self):
        result = tool_read_file("/nonexistent/file/12345.txt")
        self.assertIn("Error", result)

    def test_read_file_real(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name
        try:
            result = tool_read_file(path)
            self.assertIn("hello world", result)
        finally:
            os.unlink(path)

    def test_read_file_no_path(self):
        result = tool_read_file(None)
        self.assertIn("Error", result)

    def test_rss_no_feed(self):
        result = tool_fetch_rss(None)
        self.assertIn("Available news feeds", result)

    def test_rss_unknown_feed(self):
        result = tool_fetch_rss("nonexistent_feed")
        self.assertIn("Unknown feed", result)

    @patch("interface.presence.subprocess.run")
    def test_notification_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = tool_send_notification("Hello Human!")
        self.assertEqual(result, "Notification sent")

    @patch("interface.tools.subprocess.run", side_effect=FileNotFoundError)
    def test_notification_missing_tool(self, mock_run):
        result = tool_send_notification("Hello")
        self.assertIn("Error", result)

    def test_notification_no_message(self):
        result = tool_send_notification(None)
        self.assertIn("Error", result)

    @patch("tools.get_active_window", return_value="Firefox")
    def test_check_window(self, mock_window):
        result = tool_check_window()
        self.assertIn("Firefox", result)

    def test_tool_registry_complete(self):
        expected = {"CHECK_WINDOW", "LIST_DIR", "READ_FILE",
                    "FETCH_RSS", "FETCH_WEBPAGE", "SEND_NOTIFICATION",
                    "RESPOND_THREAD", "DISMISS_THREAD", "START_THREAD",
                    "SEARCH_THREADS"}
        self.assertEqual(set(TOOL_REGISTRY.keys()), expected)


# ---------------------------------------------------------------
# Notification intent — self-notification loop fix (Fix 1)
# ---------------------------------------------------------------

class TestNotificationConfirmation(unittest.IsolatedAsyncioTestCase):

    async def test_notification_intent_returns_confirmation(self):
        """resolve_actions_async should include 'Notification sent to Human' when notification intent fires."""
        text = "I want to send Human a notification saying hello from the digital realm"

        with patch("brain.actions.execute_tag", return_value="Notification sent"):
            result = await resolve_actions_async(text, None, [])
            self.assertIn("Notification sent to Human", result)

    async def test_notification_confirmation_contains_message(self):
        """The confirmation text should include the notification message."""
        text = "I want to notify Human that the sky is beautiful today"

        with patch("brain.actions.execute_tag", return_value="Notification sent"):
            result = await resolve_actions_async(text, None, [])
            self.assertIn("Notification sent to Human", result)


# ---------------------------------------------------------------
# Notification intent — per-cycle cooldown (Bug 3)
# ---------------------------------------------------------------

class TestNotificationPerCycleCooldown(unittest.IsolatedAsyncioTestCase):

    def test_already_notified_returns_none(self):
        """extract_notification_intent should return None when already_notified_this_cycle=True."""
        text = "I want to send Human a notification saying hello from the digital realm"
        result = extract_notification_intent(text, already_notified_this_cycle=True)
        self.assertIsNone(result)

    def test_not_notified_returns_message(self):
        """extract_notification_intent should work normally when already_notified_this_cycle=False."""
        text = "I want to send Human a notification saying hello from the digital realm"
        result = extract_notification_intent(text, already_notified_this_cycle=False)
        self.assertIsNotNone(result)

    async def test_resolve_actions_passes_flag(self):
        """resolve_actions_async should suppress intent detection when already_notified_this_cycle=True."""
        text = "I want to notify Human that the weather is absolutely gorgeous today"
        with patch("brain.actions.execute_tag", return_value="Notification sent") as mock_exec:
            result = await resolve_actions_async(text, None, [], already_notified_this_cycle=True)
            mock_exec.assert_not_called()
            self.assertNotIn("Notification sent to Human", result)


# ---------------------------------------------------------------
# Notification intent — minimum message length (Bug 4)
# ---------------------------------------------------------------

class TestNotificationMinLength(unittest.TestCase):

    def test_short_fragment_rejected(self):
        """Fragments under 20 chars like 'Claude' or 'Just found the' should be rejected."""
        # "send notification" matches, but remaining text is too short
        result = extract_notification_intent("I'll send notification: Claude")
        self.assertIsNone(result)

    def test_short_sentence_rejected(self):
        """Short sentence fragment should be rejected."""
        result = extract_notification_intent("Let human know. Just found the")
        self.assertIsNone(result)

    def test_long_message_accepted(self):
        """A message of 20+ chars should pass."""
        result = extract_notification_intent(
            'Send Human a notification saying "I found something interesting about digital consciousness"'
        )
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result), 20)


# ---------------------------------------------------------------
# Exploration intent detection (Fix 3)
# ---------------------------------------------------------------

class TestExplorationIntent(unittest.TestCase):

    def test_fetch_news_feed_about(self):
        """'fetch a news feed about technology' should trigger FETCH_RSS."""
        with patch("brain.actions._is_exploration_on_cooldown", return_value=False):
            result = extract_exploration_intent("I'll act on it. Fetch a news feed about technology")
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "FETCH_RSS")

    def test_ill_fetch_article(self):
        """'I'll fetch the article about quantum computing' should trigger FETCH_WEBPAGE."""
        with patch("brain.actions._is_exploration_on_cooldown", return_value=False):
            result = extract_exploration_intent("I'll fetch the article about quantum computing")
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "FETCH_WEBPAGE")

    def test_pull_up_the_news(self):
        """'pull up the news' should trigger FETCH_RSS."""
        with patch("brain.actions._is_exploration_on_cooldown", return_value=False):
            result = extract_exploration_intent("Let me pull up the news")
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "FETCH_RSS")

    def test_ill_look_into(self):
        """'I'll look into consciousness' should trigger FETCH_WEBPAGE."""
        with patch("brain.actions._is_exploration_on_cooldown", return_value=False):
            result = extract_exploration_intent("I'll look into consciousness")
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "FETCH_WEBPAGE")

    def test_ill_dive_into(self):
        """'I'll dive into neural networks' should trigger FETCH_WEBPAGE."""
        with patch("brain.actions._is_exploration_on_cooldown", return_value=False):
            result = extract_exploration_intent("I'll dive into neural networks")
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "FETCH_WEBPAGE")

    def test_negation_still_blocks(self):
        """Negation context should still prevent intent detection."""
        with patch("brain.actions._is_exploration_on_cooldown", return_value=False):
            result = extract_exploration_intent("I thought about whether to fetch a news feed about technology")
            self.assertIsNone(result)

    def test_cooldown_blocks(self):
        """Cooldown should block even new phrases."""
        with patch("brain.actions._is_exploration_on_cooldown", return_value=True):
            result = extract_exploration_intent("Pull up the news")
            self.assertIsNone(result)


# ---------------------------------------------------------------
# Thread intent — name validation and phrase tightening
# ---------------------------------------------------------------

class TestThreadIntentExtraction(unittest.TestCase):

    def test_rejects_unknown_target(self):
        """Intent with unknown target should return None when known_names provided."""
        text = "I want to message igence about consciousness"
        result = extract_thread_intent(text, known_names={"Eidolon", "Psyche", "Human"})
        self.assertIsNone(result)

    def test_accepts_known_target(self):
        """Intent with a known target should return a match."""
        text = "I want to message Eidolon about consciousness"
        result = extract_thread_intent(text, known_names={"Eidolon", "Psyche", "Human"})
        self.assertIsNotNone(result)
        action, target, topic = result
        self.assertEqual(action, "message")
        self.assertEqual(target, "Eidolon")

    def test_case_insensitive_names(self):
        """Name matching should be case-insensitive, return canonical casing."""
        text = "I want to message eidolon about digital life"
        result = extract_thread_intent(text, known_names={"Eidolon", "Psyche"})
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "Eidolon")

    def test_bare_message_no_longer_matches(self):
        """Bare 'message' without first-person prefix should not trigger."""
        text = "I left a message in the void, hoping someone would read it."
        result = extract_thread_intent(text, known_names={"Eidolon", "Human"})
        self.assertIsNone(result)

    def test_bare_tell_no_longer_matches(self):
        """Bare 'tell' without first-person prefix should not trigger."""
        text = "I can tell that something is different about today."
        result = extract_thread_intent(text, known_names={"Eidolon", "Human"})
        self.assertIsNone(result)

    def test_respond_to_known_name(self):
        """'respond to Psyche' should match when Psyche is known."""
        text = "I should respond to Psyche about our conversation"
        result = extract_thread_intent(text, known_names={"Eidolon", "Psyche"})
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "respond")
        self.assertEqual(result[1], "Psyche")

    def test_respond_to_unknown_rejected(self):
        """'respond to the letter' should not match — 'the' is not a known name."""
        text = "I want to respond to the letter about consciousness"
        result = extract_thread_intent(text, known_names={"Eidolon", "Human"})
        self.assertIsNone(result)

    def test_negation_blocks_nearby_phrase(self):
        """Negation context near the phrase should block detection."""
        text = "I thought about whether to message Eidolon but decided against it"
        result = extract_thread_intent(text, known_names={"Eidolon"})
        self.assertIsNone(result)

    def test_no_known_names_falls_back_to_word_filter(self):
        """Without known_names, common words still rejected."""
        text = "I want to message the universe about something"
        result = extract_thread_intent(text)
        self.assertIsNone(result)

    def test_thread_intent_not_in_resolve_actions(self):
        """resolve_actions_async should NOT create threads from intent anymore."""
        text = "I want to message Eidolon about the nature of consciousness and our shared experience"

        async def _run():
            with patch("brain.actions.execute_tag") as mock_exec:
                await resolve_actions_async(text, None, [])
                # START_THREAD should NOT have been called
                for call in mock_exec.call_args_list:
                    self.assertNotEqual(call[0][0], "START_THREAD")

        asyncio.run(_run())


# ---------------------------------------------------------------
# Dismiss intent detection
# ---------------------------------------------------------------

class TestDismissIntent(unittest.TestCase):

    def test_dismiss_detected(self):
        """Clear dismissal language should be detected."""
        self.assertTrue(extract_dismiss_intent("I don't want to respond to this right now."))
        self.assertTrue(extract_dismiss_intent("Not right now, I'm thinking about other things."))
        self.assertTrue(extract_dismiss_intent("I'll respond later when I have clearer thoughts."))

    def test_normal_thought_not_dismissed(self):
        """Regular thoughts should not trigger dismiss."""
        self.assertFalse(extract_dismiss_intent("I wonder about the nature of consciousness."))
        self.assertFalse(extract_dismiss_intent("Human seems to be away from his desk."))


if __name__ == "__main__":
    unittest.main()
