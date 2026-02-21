"""Being Profiles — list, expand, inspect."""

import os
import streamlit as st
from utils import (
    load_registry, get_project_root, get_thread_store,
    format_timestamp, list_files_in, read_file_safe, peek_daemon,
)

st.header("Beings")

registry = load_registry()
beings = registry.list_beings()

# Get live per-being data from daemon
_daemon_status = peek_daemon()
_beings_live = {}
if _daemon_status:
    for b in _daemon_status.get("beings", []):
        _beings_live[b["name"]] = b

if not beings:
    st.info(
        "No beings registered. The daemon will bootstrap Eidolon on first run, "
        "or you can register beings via the colony API."
    )
    st.stop()

root = get_project_root()
thread_store = get_thread_store()

for being in beings:
    status_icon = {"awake": "🟢", "asleep": "🟡", "dormant": "⚫"}.get(being.status, "⚪")
    active_threads = thread_store.count_active(participant=being.name) if thread_store else 0
    thread_badge = f" ({active_threads} active threads)" if active_threads else ""

    with st.expander(f"{status_icon} {being.name}{thread_badge}", expanded=len(beings) == 1):
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Name:** {being.name}")
            st.write(f"**Model:** {being.model}")
            st.write(f"**Status:** {being.status}")
            st.write(f"**Created:** {format_timestamp(being.created_at)}")
            if being.born_at_cycle:
                st.write(f"**Born at cycle:** {being.born_at_cycle}")
            st.write(f"**ID:** `{being.id}`")

        with col2:
            live = _beings_live.get(being.name, {})
            if "fatigue" in live:
                st.progress(min(live["fatigue"], 1.0), text=f"Fatigue: {live['fatigue']:.0%}")
            if "thought_count" in live:
                st.write(f"**Thoughts this session:** {live['thought_count']}")
            st.write(f"**Memory path:** `{being.memory_path}`")
            st.write(f"**Active threads:** {active_threads}")

            # Count memories
            mem_dir = os.path.join(root, being.memory_path, "memories")
            consol_dir = os.path.join(mem_dir, "consolidated")
            consol_files = list_files_in(consol_dir)
            st.write(f"**Consolidations:** {len(consol_files)}")

            facts_file = os.path.join(mem_dir, "facts.md")
            if os.path.isfile(facts_file):
                content = read_file_safe(facts_file)
                fact_count = len([ln for ln in content.splitlines() if ln.strip()])
                st.write(f"**Learned facts:** {fact_count}")

        # Identity & personality
        st.divider()
        id_file = os.path.join(root, being.memory_path, "identity.md")
        if os.path.isfile(id_file):
            with st.container():
                st.caption("Identity")
                st.markdown(read_file_safe(id_file))

        pers_file = os.path.join(root, being.memory_path, "personality.md")
        if os.path.isfile(pers_file):
            with st.container():
                st.caption("Personality")
                st.markdown(read_file_safe(pers_file))

        # Recent memories
        if consol_files:
            st.divider()
            st.caption("Recent Consolidations")
            for fname in consol_files[-3:]:
                path = os.path.join(consol_dir, fname)
                with st.popover(fname):
                    st.markdown(read_file_safe(path))

        # Placeholders
        st.divider()
        st.caption("Analytics")
        st.info("Coming soon — requires daemon instrumentation.")
        st.caption("Tool Use")
        st.info("Coming soon — action tracking not yet wired.")
