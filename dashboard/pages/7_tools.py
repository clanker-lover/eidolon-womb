"""Tool Use — per-being tool invocation stats."""

import os
import streamlit as st
from utils import load_registry, get_project_root, list_files_in, read_file_safe

import sys
sys.path.insert(0, str(get_project_root()))
from core.stats import get_all_stats

st.header("Tool Use")

root = get_project_root()
registry = load_registry()
stats = get_all_stats(root)

# --- Counters ---
if not stats:
    st.info("No data yet. Tool use stats accumulate as beings invoke actions.")
else:
    for being in registry.list_beings():
        being_stats = stats.get(being.id, {})
        tool_count = being_stats.get("tool_use", 0)
        if tool_count:
            st.metric(f"{being.name} — Tool Uses", tool_count)
        else:
            st.caption(f"{being.name} — no tool use recorded yet")

# --- Recent logs ---
st.divider()
st.subheader("Recent Logs")
st.caption("Action execution entries from being log files.")

beings = registry.list_beings()
for being in beings:
    log_dir = os.path.join(root, being.memory_path, "logs")
    log_files = list_files_in(log_dir)
    if not log_files:
        continue

    latest_log = os.path.join(log_dir, log_files[-1])
    content = read_file_safe(latest_log)
    if not content:
        continue

    # Filter to lines mentioning tool/action execution
    tool_lines = [ln for ln in content.splitlines() if any(k in ln.lower() for k in ["tool", "action", "tag", "intent-detected", "exploration"])]
    if tool_lines:
        with st.expander(f"{being.name} — {log_files[-1]}"):
            st.code("\n".join(tool_lines[-20:]), language="text")
