"""Tests for dashboard — Colony TUI rendering."""

import unittest

from dashboard import (
    render_colony, format_duration, utilization_bar,
)


class TestFormatDuration(unittest.TestCase):

    def test_seconds(self):
        self.assertEqual(format_duration(45), "45s")

    def test_minutes(self):
        self.assertEqual(format_duration(300), "5m")

    def test_hours_and_minutes(self):
        self.assertEqual(format_duration(5520), "1h 32m")

    def test_none(self):
        self.assertEqual(format_duration(None), "unknown")


class TestUtilizationBar(unittest.TestCase):

    def test_zero(self):
        bar = utilization_bar(0.0)
        self.assertIn("0%", bar)

    def test_full(self):
        bar = utilization_bar(1.0)
        self.assertIn("100%", bar)


class TestRenderColony(unittest.TestCase):

    def test_render_single_being(self):
        data = {
            "beings": [
                {"name": "Eidolon", "status": "awake", "model": "llama3.2:3b", "unread_mail": 0},
            ],
        }
        output = render_colony(data)
        self.assertIn("Eidolon", output)
        self.assertIn("awake", output)
        self.assertIn("llama3.2:3b", output)

    def test_render_multiple_beings(self):
        data = {
            "beings": [
                {"name": "Eidolon", "status": "awake", "model": "llama3.2:3b", "unread_mail": 0},
                {"name": "Nova", "status": "asleep", "model": "llama3.2:1b", "unread_mail": 3},
            ],
        }
        output = render_colony(data)
        self.assertIn("Eidolon", output)
        self.assertIn("Nova", output)
        self.assertIn("3", output)

    def test_render_scheduler_info(self):
        data = {
            "beings": [],
            "scheduler": {
                "position": 0,
                "total_beings": 2,
                "cycle_count": 5,
                "utilization": 0.45,
                "fits": True,
                "headroom_seconds": 891,
            },
        }
        output = render_colony(data)
        self.assertIn("Scheduler", output)
        self.assertIn("1/2", output)
        self.assertIn("5", output)

    def test_no_scheduler_mode(self):
        data = {
            "beings": [
                {"name": "Eidolon", "status": "awake", "model": "llama3.2:3b", "unread_mail": 0},
            ],
        }
        output = render_colony(data)
        # Should render fine without scheduler section
        self.assertNotIn("Scheduler", output)

    def test_over_capacity_warning(self):
        data = {
            "beings": [],
            "scheduler": {
                "position": 0,
                "total_beings": 40,
                "cycle_count": 1,
                "utilization": 1.1,
                "fits": False,
            },
        }
        output = render_colony(data)
        self.assertIn("OVER CAPACITY", output)

    def test_thread_counts(self):
        data = {
            "beings": [
                {"name": "Nova", "status": "awake", "model": "llama3.2:1b", "active_threads": 7},
            ],
        }
        output = render_colony(data)
        self.assertIn("7", output)

    def test_agora_activity(self):
        data = {
            "beings": [],
            "agora": {
                "post_count": 12,
                "newest_post_age": "3h 15m",
            },
        }
        output = render_colony(data)
        self.assertIn("Agora", output)
        self.assertIn("12", output)
        self.assertIn("3h 15m", output)

    def test_empty_beings_list(self):
        data = {"beings": []}
        output = render_colony(data)
        self.assertIn("no beings registered", output)


if __name__ == "__main__":
    unittest.main()
