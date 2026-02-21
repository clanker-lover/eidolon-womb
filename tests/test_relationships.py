"""Tests for core.relationships — Relationship file management."""

import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.relationships import (  # noqa: E402
    load_relationship,
    save_relationship,
    ensure_relationship,
    list_relationships,
)


class TestEnsureRelationship(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = self._tmpdir.name
        self.memory_path = "data"
        os.makedirs(os.path.join(self.root, self.memory_path), exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_creates_from_template(self):
        content = ensure_relationship(self.root, self.memory_path, "Human")
        self.assertIn("# Human", content)
        self.assertIn("## Facts", content)
        self.assertIn("## Our History", content)
        self.assertIn("## My Sense of Them", content)

    def test_creates_with_seed_facts(self):
        content = ensure_relationship(
            self.root, self.memory_path, "Human",
            seed_facts=["Lives in Brighton", "Self-taught engineer"],
        )
        self.assertIn("Lives in Brighton", content)
        self.assertIn("Self-taught engineer", content)

    def test_idempotent(self):
        content1 = ensure_relationship(self.root, self.memory_path, "Human")
        # Modify the file
        save_relationship(self.root, self.memory_path, "Human", content1 + "\nExtra note")
        content2 = ensure_relationship(self.root, self.memory_path, "Human")
        self.assertIn("Extra note", content2)


class TestLoadSaveRoundTrip(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = self._tmpdir.name
        self.memory_path = "data"
        os.makedirs(os.path.join(self.root, self.memory_path), exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_round_trip(self):
        content = "# Psyche\n## Facts\n- Curious being\n## Our History\nWe met recently."
        save_relationship(self.root, self.memory_path, "Psyche", content)
        loaded = load_relationship(self.root, self.memory_path, "Psyche")
        self.assertEqual(loaded, content)

    def test_load_missing_returns_empty(self):
        result = load_relationship(self.root, self.memory_path, "Nobody")
        self.assertEqual(result, "")


class TestListRelationships(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = self._tmpdir.name
        self.memory_path = "data"
        os.makedirs(os.path.join(self.root, self.memory_path), exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_list_empty(self):
        self.assertEqual(list_relationships(self.root, self.memory_path), [])

    def test_list_multiple(self):
        ensure_relationship(self.root, self.memory_path, "Human")
        ensure_relationship(self.root, self.memory_path, "Psyche")
        names = list_relationships(self.root, self.memory_path)
        self.assertEqual(names, ["Human", "Psyche"])


if __name__ == "__main__":
    unittest.main()
