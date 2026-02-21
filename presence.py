"""Backward-compat stub. Real module: interface.presence"""
import sys
from interface import presence as _real
sys.modules[__name__] = _real

# Re-export for mypy (sys.modules swap is invisible to static analysis)
get_presence_status = _real.get_presence_status
get_brandon_status = _real.get_brandon_status
get_pending_replies = _real.get_pending_replies
is_brandon_away = _real.is_brandon_away
