"""Backward-compat stub. Real module: interface.tools"""

import sys
from interface import tools as _real

sys.modules[__name__] = _real

# Re-export for mypy (sys.modules swap is invisible to static analysis)
TOOL_REGISTRY = _real.TOOL_REGISTRY
RSS_FEEDS = _real.RSS_FEEDS
tool_fetch_webpage = _real.tool_fetch_webpage
tool_fetch_rss = _real.tool_fetch_rss
fire_notify_send = _real.fire_notify_send
