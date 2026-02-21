"""Tool Use — tool invocation stats."""

import os
import streamlit as st
from utils import get_project_root, list_files_in, read_file_safe

import sys

sys.path.insert(0, str(get_project_root()))
from core.stats import get_all_stats

st.header("Tool Use")

root = get_project_root()
stats = get_all_stats(root)

# --- Counters ---
if not stats:
    st.info("No data yet. Tool use stats accumulate as the being invokes actions.")
else:
    for being_id, being_stats in stats.items():
        tool_count = being_stats.get("tool_use", 0)
        if tool_count:
            st.metric("Tool Uses", tool_count)
        else:
            st.caption("No tool use recorded yet")

# --- Recent logs ---
st.divider()
st.subheader("Recent Logs")
st.caption("Action execution entries from log files.")

log_dir = os.path.join(root, "data", "logs")
log_files = list_files_in(log_dir)

if log_files:
    latest_log = os.path.join(log_dir, log_files[-1])
    content = read_file_safe(latest_log)
    if content:
        tool_lines = [
            ln
            for ln in content.splitlines()
            if any(
                k in ln.lower()
                for k in ["tool", "action", "tag", "intent-detected", "exploration"]
            )
        ]
        if tool_lines:
            with st.expander(log_files[-1]):
                st.code("\n".join(tool_lines[-20:]), language="text")
        else:
            st.info("No tool-related entries in latest log.")
else:
    st.info("No log files found.")
