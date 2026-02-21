"""Eidolon Admin Dashboard — entry point and sidebar."""

import streamlit as st
from utils import load_registry, peek_daemon, send_turbo, format_timestamp, get_total_cycles, get_thread_store

st.set_page_config(
    page_title="Eidolon",
    page_icon=":::",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
with st.sidebar:
    st.title("Eidolon")
    st.caption("Colony Admin Console")
    st.divider()

    # Daemon status
    status = peek_daemon()
    if status:
        st.success("Daemon connected")
    else:
        st.error("Daemon offline")

    # Being count
    registry = load_registry()
    beings = registry.list_beings()
    st.metric("Beings", len(beings))

    if beings:
        awake = [b for b in beings if b.status == "awake"]
        if awake:
            st.caption(f"Active: {awake[0].name}")
        else:
            st.caption("All beings asleep")

# --- Unread thread messages ---
thread_store = get_thread_store()
if "dismissed_notifications" not in st.session_state:
    st.session_state.dismissed_notifications = set()

unread: list[tuple[str, str, str, str, str]] = []  # subject, author, content, msg_key, thread_id
for thread in thread_store.list_threads(participant="Brandon"):
    for msg in thread.messages:
        if msg.author != "Brandon" and "Brandon" not in (msg.read_by or []):
            msg_key = f"{thread.id}:{msg.timestamp}:{msg.author}"
            if msg_key not in st.session_state.dismissed_notifications:
                unread.append((thread.subject, msg.author, msg.content, msg_key, thread.id))

if unread:
    notif_col, dismiss_col = st.columns([6, 1])
    with notif_col:
        st.warning(
            f"📬 **{len(unread)} unread message{'s' if len(unread) != 1 else ''}** in Threads"
        )
    with dismiss_col:
        if st.button("✕ Dismiss", key="dismiss_all_notifs"):
            for _, _, _, key, _ in unread:
                st.session_state.dismissed_notifications.add(key)
            st.rerun()
    for subj, author, content, _, _ in unread[:5]:
        st.caption(f"**{author}** in _{subj}_ — \"{content[:80]}{'…' if len(content) > 80 else ''}\"")
    if len(unread) > 5:
        st.caption(f"…and {len(unread) - 5} more")

# --- Main page ---
st.header("Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Colony")
    if beings:
        for b in beings:
            display_status = {"awake": "active", "asleep": "asleep", "dormant": "dormant"}.get(b.status, b.status)
            icon = {"awake": "🟢", "asleep": "🟡", "dormant": "⚫"}.get(b.status, "⚪")
            st.write(f"{icon} **{b.name}** — {display_status}")
    else:
        st.info("No beings registered yet. Bootstrap Eidolon from the daemon to get started.")

with col2:
    st.subheader("Daemon")
    # Prefer live cycle count from daemon; fall back to local stats.json
    if status and "total_cycles" in status:
        total_cycles = status["total_cycles"]
    else:
        total_cycles = get_total_cycles()
    interval = status.get("thought_interval", 1620) if status else 1620
    turbo_on = status.get("turbo", False) if status else False
    state_val = status.get("state", "unknown") if status else "unknown"

    # Sleep takes priority — can't be turbo/paused while asleep
    if state_val == "asleep":
        active = "normal"
        mode_label = "sleeping"
    elif turbo_on and interval <= 10:
        active = "turbo"
        mode_label = "cycling (turbo)"
    elif turbo_on and interval >= 86400:
        active = "pause"
        mode_label = "stasis"
    else:
        active = "normal"
        if state_val == "awake-busy":
            mode_label = "thinking"
        else:
            interval_min = interval // 60
            mode_label = f"idle ({interval_min}m cycle)"

    if status:
        st.write(f"**Status:** {mode_label}")
        # Per-being fatigue
        for b in status.get("beings", []):
            st.progress(min(b["fatigue"], 1.0), text=f"{b['name']}: {b['fatigue']:.0%}")
        if "thought_count" in status:
            st.write(f"**Thoughts this session:** {status['thought_count']}")
        if "sleep_time" in status:
            st.write(f"**Last sleep:** {format_timestamp(status['sleep_time'])}")
    else:
        st.warning("Cannot reach daemon at 10.0.0.91:7777")

    st.divider()
    st.write(f"**Cycle {total_cycles}**")
    t1, t2, t3 = st.columns(3)
    with t1:
        if st.button("Turbo", use_container_width=True, type="primary" if active == "turbo" else "secondary"):
            send_turbo(10)
            st.rerun()
    with t2:
        if st.button("Normal", use_container_width=True, type="primary" if active == "normal" else "secondary"):
            send_turbo("off")
            st.rerun()
    with t3:
        if st.button("Pause", use_container_width=True, type="primary" if active == "pause" else "secondary"):
            send_turbo(86400)
            st.rerun()

with col3:
    st.subheader("Quick Stats")
    import os
    root = os.path.expanduser("~/eidolon")
    conv_dir = os.path.join(root, "data", "conversations")
    if os.path.isdir(conv_dir):
        convs = [f for f in os.listdir(conv_dir) if f.endswith(".md") and not f.endswith(("_summary.md", "_notes.md"))]
        st.metric("Conversations", len(convs))
    mem_file = os.path.join(root, "data", "memories", "facts.md")
    if os.path.isfile(mem_file):
        with open(mem_file) as f:
            facts = [ln for ln in f.readlines() if ln.strip()]
        st.metric("Learned Facts", len(facts))
    consol_dir = os.path.join(root, "data", "memories", "consolidated")
    if os.path.isdir(consol_dir):
        st.metric("Consolidations", len(os.listdir(consol_dir)))
