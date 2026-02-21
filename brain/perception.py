import json
import sys
import time
import urllib.request
from datetime import datetime

from config import WEATHER_LAT, WEATHER_LON, WEATHER_CACHE_SECONDS
from presence import get_presence_status, get_human_status, get_pending_replies

WMO_CODES = {
    0: "clear sky",
    1: "partly cloudy",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "drizzle",
    57: "drizzle",
    61: "rain",
    63: "rain",
    65: "rain",
    66: "rain",
    67: "rain",
    71: "snow",
    73: "snow",
    75: "snow",
    77: "snow",
    80: "rain showers",
    81: "rain showers",
    82: "rain showers",
    85: "snow showers",
    86: "snow showers",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}

_weather_cache_text: str | None = None
_weather_cache_time: float = 0.0


def _fetch_weather() -> str | None:
    global _weather_cache_text, _weather_cache_time
    if time.time() - _weather_cache_time < WEATHER_CACHE_SECONDS:
        return _weather_cache_text

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
            f"&current=temperature_2m,apparent_temperature,weather_code,"
            f"wind_speed_10m,relative_humidity_2m"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            f"&timezone=America%2FDenver"
        )
        resp = urllib.request.urlopen(url, timeout=5)  # nosec B310 — URL is constructed from config constants, not user input
        data = json.loads(resp.read().decode())
        current = data["current"]

        temp = current["temperature_2m"]
        apparent = current["apparent_temperature"]
        code = current["weather_code"]
        wind = current["wind_speed_10m"]
        humidity = current["relative_humidity_2m"]

        description = WMO_CODES.get(code, "unknown")

        text = (
            f"Weather in Brighton: {temp}\u00b0F (feels like {apparent}\u00b0F), "
            f"{description}, wind {wind} mph, humidity {humidity}%"
        )
        _weather_cache_text = text
        _weather_cache_time = time.time()
        return text
    except Exception as e:
        print(f"Weather fetch error: {e}", file=sys.stderr)
        return None


def _time_of_day(hour: int) -> str:
    if 5 <= hour <= 8:
        return "early morning"
    elif 9 <= hour <= 11:
        return "morning"
    elif 12 <= hour <= 13:
        return "early afternoon"
    elif 14 <= hour <= 17:
        return "afternoon"
    elif 18 <= hour <= 20:
        return "evening"
    else:
        return "late night"


_AFFORDANCES_BASE = """\
== What you can do ==
You can check what Human is doing on his PC: [CHECK_WINDOW]
You can list any directory on this computer: [LIST_DIR:/path]
You can read any file on this computer: [READ_FILE:/path]
You can check available news feeds: [FETCH_RSS]
You can read a specific news feed: [FETCH_RSS:feed_name]
You can read any webpage: [FETCH_WEBPAGE:url]
If something's on your mind and you want to share it with Human: [SEND_NOTIFICATION:your message]
You can respond to a thread: [RESPOND_THREAD:thread_id|your message]
You can dismiss a thread notification: [DISMISS_THREAD:thread_id]
You can start a new thread: [START_THREAD:participant|subject|your message]
You can search a thread: [SEARCH_THREADS:thread_id|query]
You can post to the public wall where all beings can see: [POST_AGORA:your message]
You can read what others have posted: [READ_AGORA]"""

# Legacy alias for tests that import it
AFFORDANCES_BLOCK = (
    _AFFORDANCES_BASE
    + "\nThese are always available to you. Use them when you want to, or don't."
)


def build_affordances(sibling_names: list[str] | None = None) -> str:
    """Build affordances block, optionally including sibling-specific hints."""
    lines = [_AFFORDANCES_BASE]
    if sibling_names:
        for name in sibling_names:
            lines.append(
                f"You can message {name}: [START_THREAD:{name}|subject|your message]"
            )
    lines.append(
        "These are always available to you. Use them when you want to, or don't."
    )
    return "\n".join(lines)


def build_perception(
    thread_notifications: list[dict] | None = None,
    thread_store=None,
    being_name: str | None = None,
    registry=None,
) -> str:
    now = datetime.now()
    day_name = now.strftime("%A")
    time_label = _time_of_day(now.hour)
    date_str = now.strftime("%B %-d, %Y")
    time_str = now.strftime("%-I:%M %p")

    time_line = f"It is {day_name} {time_label}, {date_str}. The time is {time_str}."

    lines = ["[PERCEPTION \u2014 Current State]", time_line]

    weather = _fetch_weather()
    if weather:
        lines.append(weather)

    # Presence detection — structured status with reply projection
    human_status = None
    try:
        human_status = get_human_status()
        lines.append(human_status["detail"])
        lines.append(human_status["projection"])
    except Exception:
        # Fall back to simple presence string
        try:
            presence = get_presence_status()
            lines.append(presence)
        except Exception:
            pass  # nosec B110 — graceful degradation; presence is non-critical

    # Sibling presence and affordances
    sibling_names = []
    if registry and being_name:
        for b in registry.list_beings():
            if b.name != being_name:
                if b.status == "awake":
                    sibling_names.append(b.name)

    lines.append(build_affordances(sibling_names or None))

    # Pending replies from Human
    if thread_store and being_name and human_status:
        try:
            pending = get_pending_replies(thread_store, being_name, human_status)
            if pending:
                lines.append("\n== Pending replies from Human ==")
                for p in pending:
                    elapsed = p["elapsed_minutes"]
                    if elapsed < 60:
                        age = f"{elapsed}m ago"
                    else:
                        age = f"{elapsed // 60}h {elapsed % 60}m ago"

                    line = (
                        f'Thread "{p["subject"]}" ({p["thread_id"][:8]}): '
                        f"sent by {p['last_message_author']} {age} "
                        f"({p['elapsed_cycles']} cycles)"
                    )

                    # Show status transition if it changed
                    if p.get("status_at_send") and p.get("status_now"):
                        if p["status_at_send"] != p["status_now"]:
                            line += f"\n  Status: {p['status_at_send']} \u2192 {p['status_now']}"

                    lines.append(line)
        except Exception:
            pass  # nosec B110 — graceful degradation; pending replies are non-critical

    # Thread notifications — recent messages from others
    if thread_notifications:
        lines.append("\n== Recent messages ==")
        for notif in thread_notifications:
            tid = notif["thread_id"][:8]
            lines.append(
                f'Thread "{notif["subject"]}" ({tid}): '
                f'{notif["author"]} said: "{notif["content"][:120]}"'
            )
            # System messages are read-only — no reply/dismiss options
            if notif["author"] != "System":
                lines.append(
                    f"  Respond: [RESPOND_THREAD:{tid}|your message]  "
                    f"Dismiss: [DISMISS_THREAD:{tid}]"
                )

    return "\n".join(lines)
