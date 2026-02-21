"""Tests for core.threads — Thread system."""

import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.threads import ThreadStore, ThreadMessage  # noqa: E402


class TestThreadCRUD(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_create_thread(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Hello")
        self.assertIsNotNone(thread.id)
        self.assertEqual(sorted(thread.participants), ["Eidolon", "Human"])
        self.assertEqual(thread.subject, "Hello")
        self.assertEqual(thread.status, "active")
        self.assertEqual(thread.messages, [])

    def test_create_thread_with_initial_message(self):
        msg = ThreadMessage(
            author="Human",
            content="Hey there",
            timestamp=datetime.now().isoformat(),
        )
        thread = self.store.create_thread(["Human", "Eidolon"], "Greeting", msg)
        self.assertEqual(len(thread.messages), 1)
        self.assertEqual(thread.messages[0].content, "Hey there")

    def test_get_thread(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Test")
        loaded = self.store.get_thread(thread.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, thread.id)
        self.assertEqual(loaded.subject, "Test")

    def test_get_nonexistent_thread(self):
        self.assertIsNone(self.store.get_thread("nonexistent-id"))

    def test_append_message(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        msg = ThreadMessage(
            author="Eidolon",
            content="Hello Human",
            timestamp=datetime.now().isoformat(),
        )
        updated = self.store.append_message(thread.id, msg)
        self.assertEqual(len(updated.messages), 1)
        self.assertEqual(updated.messages[0].author, "Eidolon")
        self.assertEqual(updated.last_activity, msg.timestamp)

    def test_append_message_reactivates_dormant(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Old chat")
        self.store.update_status(thread.id, "dormant")
        msg = ThreadMessage(
            author="Human",
            content="Wake up",
            timestamp=datetime.now().isoformat(),
        )
        updated = self.store.append_message(thread.id, msg)
        self.assertEqual(updated.status, "active")

    def test_append_to_nonexistent_raises(self):
        msg = ThreadMessage(author="X", content="Y", timestamp=datetime.now().isoformat())
        with self.assertRaises(KeyError):
            self.store.append_message("bad-id", msg)


class TestThreadListing(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_list_all(self):
        self.store.create_thread(["Human", "Eidolon"], "A")
        self.store.create_thread(["Human", "Psyche"], "B")
        threads = self.store.list_threads()
        self.assertEqual(len(threads), 2)

    def test_list_by_participant(self):
        self.store.create_thread(["Human", "Eidolon"], "A")
        self.store.create_thread(["Human", "Psyche"], "B")
        self.store.create_thread(["Eidolon", "Psyche"], "C")
        eidolon_threads = self.store.list_threads(participant="Eidolon")
        self.assertEqual(len(eidolon_threads), 2)
        psyche_threads = self.store.list_threads(participant="Psyche")
        self.assertEqual(len(psyche_threads), 2)

    def test_list_by_status(self):
        t1 = self.store.create_thread(["Human", "Eidolon"], "Active")
        t2 = self.store.create_thread(["Human", "Psyche"], "Dormant")
        self.store.update_status(t2.id, "dormant")
        active = self.store.list_threads(status="active")
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].id, t1.id)

    def test_list_sorted_by_last_activity(self):
        t1 = self.store.create_thread(["Human", "Eidolon"], "Old")
        time.sleep(0.01)
        t2 = self.store.create_thread(["Human", "Psyche"], "New")
        threads = self.store.list_threads()
        self.assertEqual(threads[0].id, t2.id)
        self.assertEqual(threads[1].id, t1.id)

    def test_list_empty(self):
        self.assertEqual(self.store.list_threads(), [])


class TestThreadSearch(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_search_finds_matches(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Tech talk")
        now = datetime.now().isoformat()
        self.store.append_message(thread.id, ThreadMessage("Human", "I love Python", now))
        self.store.append_message(thread.id, ThreadMessage("Eidolon", "Python is great", now))
        self.store.append_message(thread.id, ThreadMessage("Human", "What about Rust?", now))
        results = self.store.search_thread(thread.id, "Python")
        self.assertEqual(len(results), 2)

    def test_search_max_results(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        now = datetime.now().isoformat()
        for i in range(10):
            self.store.append_message(
                thread.id, ThreadMessage("Human", f"keyword message {i}", now)
            )
        results = self.store.search_thread(thread.id, "keyword", max_results=3)
        self.assertEqual(len(results), 3)

    def test_search_case_insensitive(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        now = datetime.now().isoformat()
        self.store.append_message(thread.id, ThreadMessage("Human", "Hello World", now))
        results = self.store.search_thread(thread.id, "hello")
        self.assertEqual(len(results), 1)

    def test_search_nonexistent_thread(self):
        self.assertEqual(self.store.search_thread("bad-id", "query"), [])


class TestFindOrCreate(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_creates_when_none_exist(self):
        thread = self.store.find_or_create_thread(["Human", "Eidolon"])
        self.assertIsNotNone(thread.id)
        self.assertEqual(thread.status, "active")

    def test_finds_existing_active_thread(self):
        t1 = self.store.create_thread(["Human", "Eidolon"], "Existing")
        t2 = self.store.find_or_create_thread(["Eidolon", "Human"])
        self.assertEqual(t1.id, t2.id)

    def test_ignores_dormant_thread(self):
        t1 = self.store.create_thread(["Human", "Eidolon"], "Dormant")
        self.store.update_status(t1.id, "dormant")
        t2 = self.store.find_or_create_thread(["Human", "Eidolon"])
        self.assertNotEqual(t1.id, t2.id)

    def test_uses_custom_subject(self):
        thread = self.store.find_or_create_thread(
            ["Human", "Eidolon"], subject="Custom subject"
        )
        self.assertEqual(thread.subject, "Custom subject")


class TestRecentActivity(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_returns_messages_from_others(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        now = datetime.now().isoformat()
        self.store.append_message(
            thread.id, ThreadMessage("Eidolon", "Hello Human!", now)
        )
        activity = self.store.get_recent_activity("Human")
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0][1].author, "Eidolon")

    def test_excludes_own_messages(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        now = datetime.now().isoformat()
        self.store.append_message(
            thread.id, ThreadMessage("Human", "Hey", now)
        )
        activity = self.store.get_recent_activity("Human")
        self.assertEqual(len(activity), 0)

    def test_since_filter(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        new_time = datetime.now().isoformat()
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
        self.store.append_message(
            thread.id, ThreadMessage("Eidolon", "Old message", old_time)
        )
        self.store.append_message(
            thread.id, ThreadMessage("Eidolon", "New message", new_time)
        )
        activity = self.store.get_recent_activity("Human", since=cutoff)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0][1].content, "New message")


class TestHumanAsParticipant(unittest.TestCase):
    """Human has no being_id — verify he works as a plain name participant."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_human_in_thread(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        self.assertIn("Human", thread.participants)

    def test_human_messages(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        now = datetime.now().isoformat()
        self.store.append_message(
            thread.id, ThreadMessage("Human", "Hey Eidolon", now)
        )
        self.store.append_message(
            thread.id, ThreadMessage("Eidolon", "Hello Human", now)
        )
        loaded = self.store.get_thread(thread.id)
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(loaded.messages[0].author, "Human")


class TestUpdateSummaryAndStatus(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_update_summary(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        updated = self.store.update_summary(thread.id, "They discussed weather.")
        self.assertEqual(updated.summary, "They discussed weather.")
        loaded = self.store.get_thread(thread.id)
        self.assertEqual(loaded.summary, "They discussed weather.")

    def test_update_status(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        updated = self.store.update_status(thread.id, "dormant")
        self.assertEqual(updated.status, "dormant")

    def test_invalid_status_raises(self):
        thread = self.store.create_thread(["Human", "Eidolon"], "Chat")
        with self.assertRaises(ValueError):
            self.store.update_status(thread.id, "invalid")

    def test_update_nonexistent_raises(self):
        with self.assertRaises(KeyError):
            self.store.update_summary("bad-id", "summary")
        with self.assertRaises(KeyError):
            self.store.update_status("bad-id", "active")


class TestCountActive(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ThreadStore(os.path.join(self._tmpdir.name, "threads"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_count_all_active(self):
        self.store.create_thread(["Human", "Eidolon"], "A")
        self.store.create_thread(["Human", "Psyche"], "B")
        t3 = self.store.create_thread(["Eidolon", "Psyche"], "C")
        self.store.update_status(t3.id, "dormant")
        self.assertEqual(self.store.count_active(), 2)

    def test_count_active_for_participant(self):
        self.store.create_thread(["Human", "Eidolon"], "A")
        self.store.create_thread(["Human", "Psyche"], "B")
        self.store.create_thread(["Eidolon", "Psyche"], "C")
        self.assertEqual(self.store.count_active(participant="Human"), 2)
        self.assertEqual(self.store.count_active(participant="Eidolon"), 2)


if __name__ == "__main__":
    unittest.main()
