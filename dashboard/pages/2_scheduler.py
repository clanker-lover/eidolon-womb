"""Scheduler Control — position, capacity, pause/resume."""

import streamlit as st
from utils import load_registry, load_scheduler_state, format_timestamp

st.header("Scheduler")

registry = load_registry()
beings = registry.list_beings()
sched_state = load_scheduler_state()

# --- Current State ---
st.subheader("State")

if sched_state:
    col1, col2, col3 = st.columns(3)

    active = [b for b in beings if b.status == "awake"]

    with col1:
        total = len(active)
        pos = sched_state.position
        if total > 0:
            st.metric("Position", f"{pos + 1} / {total}")
            current = active[pos % total] if active else None
            if current:
                st.caption(f"Current: **{current.name}**")
        else:
            st.metric("Position", "—")
            st.caption("No active beings")

    with col2:
        st.metric("Cycles", sched_state.cycle_count)

    with col3:
        if sched_state.last_cycle_start:
            st.write(f"**Last cycle:** {format_timestamp(sched_state.last_cycle_start)}")
        else:
            st.write("**Last cycle:** never")
else:
    st.info("No scheduler state found. The scheduler hasn't run yet.")

# --- Active Beings ---
st.subheader("Active Beings")

if beings:
    for b in beings:
        icon = {"awake": "🟢", "asleep": "🟡", "dormant": "⚫"}.get(b.status, "⚪")
        st.write(f"{icon} **{b.name}** — `{b.model}` — {b.status}")
else:
    st.info("No beings registered.")

# --- Capacity ---
st.subheader("Capacity")

active = [b for b in beings if b.status == "awake"]
if active:
    # Simple utilization estimate: each being gets ~27min/n time
    # Real capacity needs ModelProfile data which may not be available
    n = len(active)
    # Show a basic bar — real capacity math needs daemon integration
    utilization = min(n / max(n, 1), 1.0)
    st.progress(utilization, text=f"{n} active being{'s' if n != 1 else ''}")
    st.caption("Accurate capacity utilization requires daemon model profiles.")
else:
    st.progress(0.0, text="No active beings")

# --- Controls ---
st.subheader("Controls")

col1, col2 = st.columns(2)
with col1:
    if st.button("Pause Scheduler", use_container_width=True):
        st.warning("Not yet implemented — requires daemon socket command.")
with col2:
    if st.button("Resume Scheduler", use_container_width=True):
        st.warning("Not yet implemented — requires daemon socket command.")

st.divider()
st.caption("Human Review Queue")
st.info("Coming soon — no review items pending.")
