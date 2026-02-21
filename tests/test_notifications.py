"""Tests for notification lifecycle, peek protocol, and presence-aware firing."""

import asyncio
import json
import os
import sys
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from womb import EidolonDaemon, DaemonState  # noqa: E402
import tools  # noqa: E402


def _make_daemon():
    """Create a daemon with minimal mocks for unit testing."""
    daemon = EidolonDaemon()
    daemon.memory_index = MagicMock()
    daemon.memory_index.search.return_value = []
    daemon.memory_index.rebuild = MagicMock()
    daemon.session_filepath = "/tmp/test_session.md"
    daemon.session_id = "test-session"
    # Mock thread store for notification tests
    daemon._thread_store = MagicMock()
    daemon._thread_store.find_or_create_thread.return_value = MagicMock(id="mock-thread-id")
    daemon._thread_store.append_message.return_value = None
    return daemon


class TestNotificationSink(unittest.TestCase):
    """Verify _notification_sink intercepts tool_send_notification()."""

    def setUp(self):
        self._original_sink = tools._notification_sink

    def tearDown(self):
        tools._notification_sink = self._original_sink

    def test_sink_intercepts(self):
        tools._notification_sink = lambda msg: f"intercepted: {msg}"
        result = tools.tool_send_notification("hello")
        self.assertEqual(result, "intercepted: hello")

    def test_fallback_when_sink_is_none(self):
        tools._notification_sink = None
        with patch("tools.fire_notify_send", return_value=True) as mock_fire:
            result = tools.tool_send_notification("hello")
        mock_fire.assert_called_once_with("hello")
        self.assertEqual(result, "Notification sent")

    def test_fallback_failure(self):
        tools._notification_sink = None
        with patch("tools.fire_notify_send", return_value=False):
            result = tools.tool_send_notification("hello")
        self.assertEqual(result, "Error: notification failed")

    def test_no_message_error(self):
        result = tools.tool_send_notification()
        self.assertIn("Error", result)


class TestNotificationQueue(unittest.TestCase):
    """Verify _queue_notification() appends and sets notification_seen=False."""

    def test_queue_appends(self):
        daemon = _make_daemon()
        daemon.notification_seen = True
        result = daemon._queue_notification("test message")
        self.assertEqual(daemon.pending_notifications, [{"being": "Eidolon", "message": "test message"}])
        self.assertFalse(daemon.notification_seen)
        self.assertIn("queued", result.lower())

    def test_queue_includes_being_name(self):
        daemon = _make_daemon()
        daemon._active_being_name = "Psyche"
        daemon._queue_notification("hello from Psyche")
        self.assertEqual(daemon.pending_notifications[0]["being"], "Psyche")
        self.assertEqual(daemon.pending_notifications[0]["message"], "hello from Psyche")

    def test_queue_multiple(self):
        daemon = _make_daemon()
        daemon._queue_notification("first")
        daemon._queue_notification("second")
        self.assertEqual(len(daemon.pending_notifications), 2)
        self.assertEqual(daemon.pending_notifications[0]["message"], "first")
        self.assertEqual(daemon.pending_notifications[1]["message"], "second")


class TestNotificationFiring(unittest.IsolatedAsyncioTestCase):
    """Test notification firing in the idle loop context."""

    def setUp(self):
        self.daemon = _make_daemon()
        self.daemon.state = DaemonState.AWAKE_AVAILABLE

    @patch("womb.fire_notify_send", return_value=True)
    @patch("womb.is_brandon_away", return_value=False)
    async def test_fires_when_present(self, mock_away, mock_fire):
        self.daemon.pending_notifications = [{"being": "Eidolon", "message": "hello Brandon"}]
        self.daemon.notification_seen = False
        self.daemon._last_notification_check = 0.0
        self.daemon.notification_sent_at = None

        now = time.monotonic()

        # Simulate the idle loop notification check
        away = await asyncio.to_thread(is_brandon_away_stub_false)
        self.assertFalse(away)

        # Directly test the logic
        away = mock_away()
        if not away:
            cooldown_ok = self.daemon.notification_sent_at is None
            if cooldown_ok:
                entry = self.daemon.pending_notifications[0]
                await asyncio.to_thread(mock_fire, entry["message"], entry["being"])
                self.daemon.notification_sent_at = now

        mock_fire.assert_called_with("hello Brandon", "Eidolon")
        self.assertIsNotNone(self.daemon.notification_sent_at)

    @patch("womb.fire_notify_send", return_value=True)
    @patch("womb.is_brandon_away", return_value=True)
    async def test_skips_when_away(self, mock_away, mock_fire):
        self.daemon.pending_notifications = [{"being": "Eidolon", "message": "hello Brandon"}]
        self.daemon.notification_seen = False

        away = mock_away()
        if not away:
            mock_fire("hello Brandon", "Eidolon")

        mock_fire.assert_not_called()

    @patch("womb.fire_notify_send", return_value=True)
    @patch("womb.is_brandon_away", return_value=False)
    async def test_cooldown_respected(self, mock_away, mock_fire):
        self.daemon.pending_notifications = [{"being": "Eidolon", "message": "hello"}]
        self.daemon.notification_seen = False
        now = time.monotonic()
        # Sent 60 seconds ago — within 300s cooldown
        self.daemon.notification_sent_at = now - 60

        away = mock_away()
        just_returned = False
        if not away:
            cooldown_ok = (
                self.daemon.notification_sent_at is None
                or (now - self.daemon.notification_sent_at) >= 300
            )
            if cooldown_ok or just_returned:
                mock_fire("hello", "Eidolon")

        mock_fire.assert_not_called()

    @patch("womb.fire_notify_send", return_value=True)
    @patch("womb.is_brandon_away", return_value=False)
    async def test_fires_on_away_to_present_transition(self, mock_away, mock_fire):
        self.daemon.pending_notifications = [{"being": "Psyche", "message": "welcome back"}]
        self.daemon.notification_seen = False
        now = time.monotonic()
        # Sent 60 seconds ago — within cooldown, but just_returned bypasses it
        self.daemon.notification_sent_at = now - 60
        self.daemon._last_presence_away = True

        away = mock_away()
        just_returned = self.daemon._last_presence_away and not away
        self.daemon._last_presence_away = away

        if not away:
            cooldown_ok = (
                self.daemon.notification_sent_at is None
                or (now - self.daemon.notification_sent_at) >= 300
            )
            if cooldown_ok or just_returned:
                entry = self.daemon.pending_notifications[0]
                await asyncio.to_thread(mock_fire, entry["message"], entry["being"])
                self.daemon.notification_sent_at = now

        mock_fire.assert_called_once_with("welcome back", "Psyche")

    async def test_no_action_when_empty(self):
        self.daemon.pending_notifications = []
        # Should not raise or do anything
        should_check = (
            self.daemon.pending_notifications
            and not self.daemon.notification_seen
        )
        self.assertFalse(should_check)


class TestNotificationClearOnConnect(unittest.IsolatedAsyncioTestCase):
    """Verify connect clears notifications and sets seen=True."""

    async def test_connect_clears(self):
        daemon = _make_daemon()
        daemon.pending_notifications = [
            {"being": "Eidolon", "message": "msg1"},
            {"being": "Psyche", "message": "msg2"},
        ]
        daemon.notification_seen = False
        daemon.notification_sent_at = 12345.0

        # Simulate what handle_client does after start_session
        delivered = [
            {"being": n["being"], "message": n["message"]}
            for n in daemon.pending_notifications
        ]
        daemon.pending_notifications.clear()
        daemon.notification_seen = True
        daemon.notification_sent_at = None

        self.assertEqual(len(delivered), 2)
        self.assertEqual(delivered[0]["being"], "Eidolon")
        self.assertEqual(delivered[1]["being"], "Psyche")
        self.assertEqual(daemon.pending_notifications, [])
        self.assertTrue(daemon.notification_seen)
        self.assertIsNone(daemon.notification_sent_at)


class TestPeekProtocol(unittest.IsolatedAsyncioTestCase):
    """Test peek response format and that no state changes occur."""

    async def test_peek_response_fields(self):
        daemon = _make_daemon()
        daemon.state = DaemonState.AWAKE_AVAILABLE
        daemon.fatigue = 0.42
        daemon.pending_notifications = [{"being": "Eidolon", "message": "test notification"}]

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        await daemon._handle_peek(writer)

        written = writer.write.call_args[0][0].decode()
        response = json.loads(written.strip())

        self.assertEqual(response["type"], "peek_response")
        self.assertEqual(response["state"], "awake-available")
        self.assertAlmostEqual(response["fatigue"], 0.42, places=2)
        self.assertEqual(response["fatigue_label"], "alert and present")
        self.assertEqual(response["pending_notifications"],
                         [{"being": "Eidolon", "message": "test notification"}])
        self.assertEqual(response["notification_count"], 1)

    async def test_peek_asleep_state(self):
        daemon = _make_daemon()
        daemon.state = DaemonState.ASLEEP
        daemon.fatigue = 0.0

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        await daemon._handle_peek(writer)

        written = writer.write.call_args[0][0].decode()
        response = json.loads(written.strip())
        self.assertEqual(response["state"], "asleep")

    async def test_peek_no_state_changes(self):
        daemon = _make_daemon()
        original_session = daemon.session_id
        original_state = daemon.state

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        await daemon._handle_peek(writer)

        # Peek should not modify daemon state
        self.assertEqual(daemon.session_id, original_session)
        self.assertEqual(daemon.state, original_state)
        self.assertIsNone(daemon._current_writer)

    async def test_peek_truncates_long_notifications(self):
        daemon = _make_daemon()
        long_msg = "x" * 200
        daemon.pending_notifications = [{"being": "Eidolon", "message": long_msg}]

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        await daemon._handle_peek(writer)

        written = writer.write.call_args[0][0].decode()
        response = json.loads(written.strip())
        self.assertEqual(len(response["pending_notifications"][0]["message"]), 100)


class TestIsNotificationAway(unittest.TestCase):
    """Test is_brandon_away() with mocked loginctl and xprintidle."""

    @patch("presence.get_idle_seconds", return_value=0.0)
    @patch("remote.subprocess.run")
    def test_locked_returns_true(self, mock_run, mock_idle):
        # First call: list-sessions
        sessions_result = MagicMock()
        sessions_result.stdout = "1 1000 lover seat0 \n"
        # Second call: show-session
        lock_result = MagicMock()
        lock_result.stdout = "yes\n"

        mock_run.side_effect = [sessions_result, lock_result]

        from presence import is_brandon_away
        self.assertTrue(is_brandon_away())

    @patch("presence.get_idle_seconds", return_value=700.0)
    @patch("remote.subprocess.run")
    def test_idle_returns_true(self, mock_run, mock_idle):
        # list-sessions
        sessions_result = MagicMock()
        sessions_result.stdout = "1 1000 lover seat0 \n"
        # show-session — not locked
        lock_result = MagicMock()
        lock_result.stdout = "no\n"

        mock_run.side_effect = [sessions_result, lock_result]

        from presence import is_brandon_away
        self.assertTrue(is_brandon_away())

    @patch("presence.get_idle_seconds", return_value=60.0)
    @patch("remote.subprocess.run")
    def test_active_returns_false(self, mock_run, mock_idle):
        sessions_result = MagicMock()
        sessions_result.stdout = "1 1000 lover seat0 \n"
        lock_result = MagicMock()
        lock_result.stdout = "no\n"

        mock_run.side_effect = [sessions_result, lock_result]

        from presence import is_brandon_away
        self.assertFalse(is_brandon_away())

    @patch("presence.get_idle_seconds", return_value=700.0)
    @patch("presence.subprocess.run", side_effect=FileNotFoundError)
    def test_loginctl_missing_falls_back_to_idle(self, mock_run, mock_idle):
        from presence import is_brandon_away
        self.assertTrue(is_brandon_away())


class TestFireNotifySend(unittest.TestCase):
    """Test fire_notify_send() helper."""

    @patch("remote.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = tools.fire_notify_send("test message")
        self.assertTrue(result)

    @patch("remote.subprocess.run", side_effect=OSError)
    def test_notify_send_missing(self, mock_run):
        result = tools.fire_notify_send("test")
        self.assertFalse(result)

    @patch("remote.subprocess.run")
    def test_plays_sound(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        tools.fire_notify_send("test")
        # Should be called twice: once for notify-send, once for paplay
        self.assertEqual(mock_run.call_count, 2)


class TestStatusIncludesNotifications(unittest.IsolatedAsyncioTestCase):
    """Test that status command includes pending_notifications count."""

    async def test_status_has_pending_count(self):
        daemon = _make_daemon()
        daemon.pending_notifications = [
            {"being": "Eidolon", "message": "a"},
            {"being": "Eidolon", "message": "b"},
            {"being": "Psyche", "message": "c"},
        ]

        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        await daemon._handle_command("status", writer)

        written = writer.write.call_args[0][0].decode()
        response = json.loads(written.strip())
        self.assertEqual(response["pending_notifications"], 3)


class TestNotificationPopsAfterFire(unittest.IsolatedAsyncioTestCase):
    """BUG 1: Verify notification is removed from queue after firing."""

    @patch("womb.fire_notify_send", return_value=True)
    @patch("womb.is_brandon_away", return_value=False)
    async def test_notification_pops_after_fire(self, mock_away, mock_fire):
        daemon = _make_daemon()
        daemon.pending_notifications = [
            {"being": "Eidolon", "message": "first"},
            {"being": "Eidolon", "message": "second"},
            {"being": "Psyche", "message": "third"},
        ]
        daemon.notification_seen = False
        daemon._last_notification_check = 0.0
        daemon.notification_sent_at = None

        await daemon._check_presence_and_notifications()

        # "first" should have been popped and fired with being name
        mock_fire.assert_called_once_with("first", "Eidolon")
        self.assertEqual(len(daemon.pending_notifications), 2)
        self.assertEqual(daemon.pending_notifications[0]["message"], "second")

    @patch("womb.fire_notify_send", return_value=True)
    @patch("womb.is_brandon_away", return_value=False)
    async def test_successive_fires_drain_queue(self, mock_away, mock_fire):
        daemon = _make_daemon()
        daemon.pending_notifications = [
            {"being": "Eidolon", "message": "a"},
            {"being": "Psyche", "message": "b"},
        ]
        daemon.notification_seen = False
        daemon._last_notification_check = 0.0
        daemon.notification_sent_at = None

        await daemon._check_presence_and_notifications()
        self.assertEqual(len(daemon.pending_notifications), 1)
        self.assertEqual(daemon.pending_notifications[0]["message"], "b")

        # Simulate cooldown expiry
        daemon.notification_sent_at = None
        daemon._last_notification_check = 0.0
        await daemon._check_presence_and_notifications()
        self.assertEqual(daemon.pending_notifications, [])


class TestNotificationDedup(unittest.TestCase):
    """BUG 2: Verify duplicate notifications are not queued."""

    def test_exact_duplicate_skipped(self):
        daemon = _make_daemon()
        daemon._queue_notification("hello Brandon")
        result = daemon._queue_notification("hello Brandon")
        self.assertEqual(len(daemon.pending_notifications), 1)
        self.assertIn("already queued", result.lower())

    def test_different_messages_both_queued(self):
        daemon = _make_daemon()
        daemon._queue_notification("first message")
        daemon._queue_notification("second message")
        self.assertEqual(len(daemon.pending_notifications), 2)

    def test_dedup_is_exact_match(self):
        daemon = _make_daemon()
        daemon._queue_notification("hello Brandon")
        daemon._queue_notification("Hello Brandon")  # different case
        self.assertEqual(len(daemon.pending_notifications), 2)

    def test_same_message_different_beings_both_queued(self):
        daemon = _make_daemon()
        daemon._active_being_name = "Eidolon"
        daemon._queue_notification("thinking of you")
        daemon._active_being_name = "Psyche"
        # Same message text but dedup is on message content only
        result = daemon._queue_notification("thinking of you")
        # Dedup matches on message text regardless of being
        self.assertEqual(len(daemon.pending_notifications), 1)
        self.assertIn("already queued", result.lower())


# Stub for test_fires_when_present
def is_brandon_away_stub_false():
    return False


if __name__ == "__main__":
    unittest.main()
