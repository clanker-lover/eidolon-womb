"""Eidolon Womb Dashboard — entry point and sidebar."""

import os
import time
import streamlit as st
from utils import (
    peek_daemon,
    format_timestamp,
    get_total_cycles,
    get_thread_store,
    get_project_root,
    send_daemon_command,
    get_user_name,
    load_user_config,
    save_user_config,
)

st.set_page_config(
    page_title="Eidolon Womb",
    page_icon=":::",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-refresh every 15 seconds
try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(interval=15_000, key="dashboard_refresh")
except ImportError:
    pass  # pip install streamlit-autorefresh for auto-refresh

# --- Sidebar ---
with st.sidebar:
    st.title("Eidolon Womb")
    st.caption("Being Dashboard")
    st.divider()

    # Daemon status
    status = peek_daemon()
    if status:
        st.success("Daemon connected")
        beings = status.get("beings", [])
        if beings:
            b = beings[0]
            icon = "🟢" if b.get("status") == "awake" else "🟡"
            st.write(f"{icon} **{b['name']}** — {b['status']}")
    else:
        st.error("Daemon offline")

    # Settings
    with st.expander("Settings", expanded=True):
        cfg = load_user_config()
        new_name = st.text_input(
            "Your name",
            value=cfg.get("user_name", ""),
            placeholder="Human",
            key="settings_user_name",
        )
        if st.button("Save", key="settings_save"):
            cfg["user_name"] = new_name.strip()
            save_user_config(cfg)
            st.success("Saved")
            st.rerun()

user_name = get_user_name()

# --- Unread thread messages ---
thread_store = get_thread_store()
if "dismissed_notifications" not in st.session_state:
    st.session_state.dismissed_notifications = set()

unread: list[
    tuple[str, str, str, str, str]
] = []  # subject, author, content, msg_key, thread_id
for thread in thread_store.list_threads(participant="Human"):
    for msg in thread.messages:
        if msg.author != "Human" and "Human" not in (msg.read_by or []):
            msg_key = f"{thread.id}:{msg.timestamp}:{msg.author}"
            if msg_key not in st.session_state.dismissed_notifications:
                unread.append(
                    (thread.subject, msg.author, msg.content, msg_key, thread.id)
                )

if unread:
    notif_col, dismiss_col = st.columns([6, 1])
    with notif_col:
        st.warning(
            f"**{len(unread)} unread message{'s' if len(unread) != 1 else ''}** in Threads"
        )
    with dismiss_col:
        if st.button("Dismiss", key="dismiss_all_notifs"):
            for _, _, _, key, _ in unread:
                st.session_state.dismissed_notifications.add(key)
            st.rerun()
    for subj, author, content, _, _ in unread[:5]:
        st.caption(
            f'**{author}** in _{subj}_ — "{content[:80]}{"..." if len(content) > 80 else ""}"'
        )
    if len(unread) > 5:
        st.caption(f"...and {len(unread) - 5} more")

# --- Main page ---
st.header("Dashboard")

col1, col2 = st.columns(2)

with col1:
    # Use being's name if available, fall back to "Daemon"
    being_name = "Daemon"
    if status:
        beings = status.get("beings", [])
        if beings:
            being_name = beings[0].get("name", "Daemon")
    st.subheader(being_name)

    # Prefer live cycle count from daemon; fall back to local stats.json
    if status and "total_cycles" in status:
        total_cycles = status["total_cycles"]
    else:
        total_cycles = get_total_cycles()
    state_val = status.get("state", "unknown") if status else "unknown"

    if state_val == "asleep":
        mode_label = "sleeping"
    elif state_val == "awake-busy":
        mode_label = "thinking"
    elif state_val == "stasis":
        mode_label = "stasis (paused)"
    elif state_val in ("awake-available", "unknown") and status:
        # Calculate countdown to next thought
        last_cycle = status.get("last_cycle_time", 0)
        interval = status.get("thought_interval", 1620)
        if last_cycle > 0:
            elapsed = time.time() - last_cycle
            remaining = max(0, interval - elapsed)
            mins_left = int(remaining // 60)
            mode_label = f"next thought in {mins_left}m"
        else:
            mode_label = "idle (27m cycle)"
    else:
        mode_label = "idle (27m cycle)"

    if status:
        st.write(f"**Status:** {mode_label}")
        for b in status.get("beings", []):
            st.progress(min(b["fatigue"], 1.0), text=f"fatigue: {b['fatigue']:.0%}")
        if "thought_count" in status:
            st.write(f"**Thoughts this session:** {status['thought_count']}")
        if "sleep_time" in status:
            st.write(f"**Last sleep:** {format_timestamp(status['sleep_time'])}")
    else:
        st.warning("Cannot reach daemon")

    st.divider()
    st.write(f"**Cycle {total_cycles}**")

    # --- Control Buttons ---
    if status:
        is_normal = state_val in ("awake-available", "awake-busy")
        is_stasis = state_val == "stasis"

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            normal_type = "primary" if is_normal else "secondary"
            normal_label = "● Normal" if is_normal else "Normal"
            if st.button(
                normal_label,
                key="btn_normal",
                type=normal_type,
                use_container_width=True,
            ):
                if not is_normal:
                    send_daemon_command("normal")
                    st.rerun()
        with btn_col2:
            stasis_type = "primary" if is_stasis else "secondary"
            stasis_label = "● Stasis" if is_stasis else "Stasis"
            if st.button(
                stasis_label,
                key="btn_stasis",
                type=stasis_type,
                use_container_width=True,
            ):
                if not is_stasis:
                    send_daemon_command("stasis")
                    st.rerun()

with col2:
    st.subheader("Quick Stats")
    root = get_project_root()
    data_dir = os.path.join(root, "data")
    conv_dir = os.path.join(data_dir, "conversations")
    if os.path.isdir(conv_dir):
        convs = [
            f
            for f in os.listdir(conv_dir)
            if f.endswith(".md") and not f.endswith(("_summary.md", "_notes.md"))
        ]
        st.metric("Conversations", len(convs))
    mem_file = os.path.join(data_dir, "memories", "facts.md")
    if os.path.isfile(mem_file):
        with open(mem_file) as f:
            facts = [ln for ln in f.readlines() if ln.strip()]
        st.metric("Learned Facts", len(facts))
    consol_dir = os.path.join(data_dir, "memories", "consolidated")
    if os.path.isdir(consol_dir):
        st.metric("Consolidations", len(os.listdir(consol_dir)))
