"""Backward-compat stub. Real module: interface.presence"""

import sys
from interface import presence as _real

sys.modules[__name__] = _real

# Re-export for mypy (sys.modules swap is invisible to static analysis)
get_presence_status = _real.get_presence_status
get_human_status = _real.get_human_status
get_pending_replies = _real.get_pending_replies
is_human_away = _real.is_human_away
