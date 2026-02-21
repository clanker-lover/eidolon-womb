import os
import sys
import json
import time
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import brain.perception as perception_mod  # noqa: E402
from brain.perception import _fetch_weather, build_perception  # noqa: E402


def _mock_api_response():
    """Return a fake Open-Meteo JSON response."""
    return json.dumps({
        "current": {
            "temperature_2m": 42.5,
            "apparent_temperature": 36.1,
            "weather_code": 3,
            "wind_speed_10m": 12.3,
            "relative_humidity_2m": 55,
        }
    }).encode()


class TestFetchWeather(unittest.TestCase):

    def setUp(self):
        # Reset cache before each test
        perception_mod._weather_cache_text = None
        perception_mod._weather_cache_time = 0.0

    @patch("brain.perception.urllib.request.urlopen")
    def test_successful_fetch(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = _mock_api_response()
        mock_urlopen.return_value = mock_resp

        result = _fetch_weather()
        self.assertIsNotNone(result)
        self.assertIn("42.5", result)
        self.assertIn("feels like", result)
        self.assertIn("36.1", result)
        self.assertIn("wind", result)
        self.assertIn("12.3", result)
        self.assertIn("humidity", result)
        self.assertIn("55%", result)
        self.assertIn("overcast", result)

    @patch("brain.perception.urllib.request.urlopen")
    def test_cache_prevents_second_call(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = _mock_api_response()
        mock_urlopen.return_value = mock_resp

        result1 = _fetch_weather()
        result2 = _fetch_weather()
        self.assertEqual(result1, result2)
        mock_urlopen.assert_called_once()

    @patch("brain.perception.urllib.request.urlopen")
    def test_api_failure_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("network error")
        result = _fetch_weather()
        self.assertIsNone(result)

    @patch("brain.perception.urllib.request.urlopen")
    def test_cache_expiry(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = _mock_api_response()
        mock_urlopen.return_value = mock_resp

        # First call — populates cache
        _fetch_weather()
        self.assertEqual(mock_urlopen.call_count, 1)

        # Expire the cache
        perception_mod._weather_cache_time = time.time() - 1000

        # Second call — should re-fetch
        _fetch_weather()
        self.assertEqual(mock_urlopen.call_count, 2)


class TestBuildPerception(unittest.TestCase):

    @patch("brain.perception.get_presence_status")
    @patch("brain.perception._fetch_weather")
    def test_weather_line_present(self, mock_weather, mock_presence):
        mock_weather.return_value = "Weather in Brighton: 42.5\u00b0F (feels like 36.1\u00b0F), overcast, wind 12.3 mph, humidity 55%"
        mock_presence.return_value = "Human is at his PC, in Terminal"
        result = build_perception()
        self.assertIn("[PERCEPTION", result)
        self.assertIn("Weather in Brighton", result)
        self.assertIn("What you can do", result)
        lines = result.split("\n")
        self.assertGreater(len(lines), 3)

    @patch("brain.perception.get_presence_status")
    @patch("brain.perception._fetch_weather")
    def test_no_weather_line_when_none(self, mock_weather, mock_presence):
        mock_weather.return_value = None
        mock_presence.return_value = "Human is at his PC, in Terminal"
        result = build_perception()
        self.assertIn("[PERCEPTION", result)
        self.assertNotIn("Weather", result)
        lines = result.split("\n")
        self.assertGreater(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
