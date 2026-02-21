"""Tests for presence.py — Brandon status detection."""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from presence import (  # noqa: E402
    BrandonStatus, _in_sleep_window,
    format_send_confirmation, get_pending_replies,
)


class TestSleepWindow(unittest.TestCase):
    """Test midnight-crossing sleep window detection."""

    def test_inside_sleep_window_before_midnight(self):
        # 23:00 is inside 22:00-06:00
        now = datetime(2026, 2, 18, 23, 0)
        self.assertTrue(_in_sleep_window(now))

    def test_inside_sleep_window_after_midnight(self):
        # 03:00 is inside 22:00-06:00
        now = datetime(2026, 2, 18, 3, 0)
        self.assertTrue(_in_sleep_window(now))

    def test_outside_sleep_window_morning(self):
        # 09:00 is outside 22:00-06:00
        now = datetime(2026, 2, 18, 9, 0)
        self.assertFalse(_in_sleep_window(now))

    def test_outside_sleep_window_afternoon(self):
        # 14:00 is outside 22:00-06:00
        now = datetime(2026, 2, 18, 14, 0)
        self.assertFalse(_in_sleep_window(now))

    def test_boundary_start(self):
        # 22:00 exactly is inside
        now = datetime(2026, 2, 18, 22, 0)
        self.assertTrue(_in_sleep_window(now))

    def test_boundary_end(self):
        # 06:00 exactly is outside (end is exclusive)
        now = datetime(2026, 2, 18, 6, 0)
        self.assertFalse(_in_sleep_window(now))


class TestFormatSendConfirmation(unittest.TestCase):
    """Test send confirmation formatting."""

    def test_present_status(self):
        status = {
            "status": BrandonStatus.PRESENT,
            "projection": "within 30 min - 2.5 hrs",
            "cycle_projection": "~1-6 cycles",
        }
        result = format_send_confirmation(status)
        self.assertIn("at his PC", result)
        self.assertIn("~1-6 cycles", result)

    def test_away_status(self):
        status = {
            "status": BrandonStatus.AWAY,
            "projection": "within 3-6 hours",
            "cycle_projection": "~7-13 cycles",
        }
        result = format_send_confirmation(status)
        self.assertIn("away", result)
        self.assertIn("3-6 hours", result)

    def test_asleep_status(self):
        status = {
            "status": BrandonStatus.ASLEEP,
            "projection": "not until morning (after 6 AM)",
            "cycle_projection": "~13-18 cycles",
        }
        result = format_send_confirmation(status)
        self.assertIn("asleep", result)
        self.assertIn("morning", result)


class TestGetPendingReplies(unittest.TestCase):
    """Test pending reply detection."""

    def test_no_brandon_threads(self):
        mock_store = MagicMock()
        mock_thread = MagicMock()
        mock_thread.participants = ["Eidolon", "Psyche"]
        mock_store.list_threads.return_value = [mock_thread]

        result = get_pending_replies(mock_store, "Eidolon", {})
        self.assertEqual(result, [])

    def test_brandon_already_replied(self):
        mock_store = MagicMock()
        mock_thread = MagicMock()
        mock_thread.participants = ["Eidolon", "Brandon"]
        mock_msg = MagicMock()
        mock_msg.author = "Brandon"
        mock_thread.messages = [mock_msg]
        mock_store.list_threads.return_value = [mock_thread]

        result = get_pending_replies(mock_store, "Eidolon", {})
        self.assertEqual(result, [])

    def test_awaiting_brandon_reply(self):
        mock_store = MagicMock()
        mock_thread = MagicMock()
        mock_thread.id = "test-thread-id"
        mock_thread.subject = "Test Subject"
        mock_thread.participants = ["Eidolon", "Brandon"]
        mock_msg = MagicMock()
        mock_msg.author = "Eidolon"
        mock_msg.timestamp = datetime.now().isoformat()
        mock_msg.metadata = {"brandon_status": "Brandon is at his PC"}
        mock_thread.messages = [mock_msg]
        mock_store.list_threads.return_value = [mock_thread]

        result = get_pending_replies(mock_store, "Eidolon", {"detail": "Brandon is away"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["subject"], "Test Subject")
        self.assertEqual(result[0]["status_at_send"], "Brandon is at his PC")
        self.assertEqual(result[0]["status_now"], "Brandon is away")


class TestMetadataBackwardCompat(unittest.TestCase):
    """Test that old messages without metadata work."""

    def test_none_metadata(self):
        mock_store = MagicMock()
        mock_thread = MagicMock()
        mock_thread.id = "test-id"
        mock_thread.subject = "Old Thread"
        mock_thread.participants = ["Eidolon", "Brandon"]
        mock_msg = MagicMock()
        mock_msg.author = "Eidolon"
        mock_msg.timestamp = datetime.now().isoformat()
        mock_msg.metadata = None  # Old message, no metadata
        mock_thread.messages = [mock_msg]
        mock_store.list_threads.return_value = [mock_thread]

        result = get_pending_replies(mock_store, "Eidolon", {"detail": "Brandon is away"})
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["status_at_send"])


if __name__ == "__main__":
    unittest.main()
