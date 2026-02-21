"""Being Profile — identity, personality, memories, status."""

import os
import streamlit as st
from utils import (
    get_project_root,
    get_thread_store,
    list_files_in,
    read_file_safe,
    peek_daemon,
)

st.header("Being")

root = get_project_root()
data_dir = os.path.join(root, "data")
thread_store = get_thread_store()

# Get live data from daemon
daemon_status = peek_daemon()
being_info = None
if daemon_status:
    beings = daemon_status.get("beings", [])
    if beings:
        being_info = beings[0]

# --- Status ---
if being_info:
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Name:** {being_info['name']}")
        st.write(f"**Model:** {being_info['model']}")
        status_str = being_info.get("status", "unknown")
        icon = {"awake": "🟢", "asleep": "🟡"}.get(status_str, "⚪")
        st.write(f"**Status:** {icon} {status_str}")

    with col2:
        fatigue = being_info.get("fatigue", 0)
        st.progress(min(fatigue, 1.0), text=f"Fatigue: {fatigue:.0%}")
        if "thought_count" in being_info:
            st.write(f"**Thoughts this session:** {being_info['thought_count']}")
        active_threads = (
            thread_store.count_active(participant=being_info["name"])
            if thread_store
            else 0
        )
        st.write(f"**Active threads:** {active_threads}")

        consol_dir = os.path.join(data_dir, "memories", "consolidated")
        consol_files = list_files_in(consol_dir)
        st.write(f"**Consolidations:** {len(consol_files)}")

        facts_file = os.path.join(data_dir, "memories", "facts.md")
        if os.path.isfile(facts_file):
            content = read_file_safe(facts_file)
            fact_count = len([ln for ln in content.splitlines() if ln.strip()])
            st.write(f"**Learned facts:** {fact_count}")
else:
    st.info("Daemon offline. Connect to see live being status.")

# --- Identity & Personality ---
st.divider()

id_file = os.path.join(data_dir, "identity.md")
if os.path.isfile(id_file):
    with st.container():
        st.caption("Identity")
        st.markdown(read_file_safe(id_file))

pers_file = os.path.join(data_dir, "personality.md")
if os.path.isfile(pers_file):
    with st.container():
        st.caption("Personality")
        st.markdown(read_file_safe(pers_file))

# --- Recent Consolidations ---
consol_dir = os.path.join(data_dir, "memories", "consolidated")
consol_files = list_files_in(consol_dir)
if consol_files:
    st.divider()
    st.caption("Recent Consolidations")
    for fname in consol_files[-3:]:
        path = os.path.join(consol_dir, fname)
        with st.popover(fname):
            st.markdown(read_file_safe(path))
