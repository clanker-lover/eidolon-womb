"""Analytics — per-being statistics."""

import streamlit as st
from utils import load_registry, get_project_root, format_timestamp

import sys
sys.path.insert(0, str(get_project_root()))
from core.stats import get_all_stats

st.header("Analytics")

root = get_project_root()
registry = load_registry()
stats = get_all_stats(root)

if not stats:
    st.info("No data yet. Stats accumulate as beings think and act.")
else:
    for being in registry.list_beings():
        being_stats = stats.get(being.id, {})
        with st.expander(f"{being.name}", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Thoughts", being_stats.get("thoughts", 0))
            col2.metric("Threads Created", being_stats.get("threads_created", 0))
            col3.metric("Thread Replies", being_stats.get("thread_replies", 0))
            col4.metric("Tool Uses", being_stats.get("tool_use", 0))
            if "last_updated" in being_stats:
                st.caption(f"Last activity: {format_timestamp(being_stats['last_updated'])}")
