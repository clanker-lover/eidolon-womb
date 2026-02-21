"""Threads — communication between human and being."""

import streamlit as st
from datetime import datetime

from utils import (
    get_thread_store,
    peek_daemon,
    format_timestamp,
    format_timestamp_short,
    get_user_name,
)

st.header("Threads")

thread_store = get_thread_store()

if thread_store is None:
    st.error("Thread store not available. Ensure data/threads/ directory exists.")
    st.stop()

# Get being name from daemon (for reply routing)
_daemon_status = peek_daemon()
_being_name = None
if _daemon_status:
    beings = _daemon_status.get("beings", [])
    if beings:
        _being_name = beings[0].get("name", "Being")
_user_display_name = get_user_name()


_HISTORICAL_BEING_NAMES = {"Being", "Eidolon"}


def _display_name(author: str) -> str:
    """Map internal author names to display names."""
    if author == "Human":
        return _user_display_name
    if author in _HISTORICAL_BEING_NAMES and _being_name:
        return _being_name
    return author


def _display_subject(subject: str) -> str:
    """Replace historical being names in thread subjects with current name."""
    if not _being_name:
        return subject
    result = subject
    for old_name in _HISTORICAL_BEING_NAMES:
        if old_name != _being_name and old_name in result:
            result = result.replace(old_name, _being_name)
    return result


# --- Session state defaults ---
if "selected_thread_id" not in st.session_state:
    st.session_state.selected_thread_id = None
if "show_all_messages" not in st.session_state:
    st.session_state.show_all_messages = set()

PREVIEW_COUNT = 5


def has_unread(thread) -> bool:
    """Check if thread has unread messages for Human."""
    for msg in thread.messages:
        if msg.author != "Human" and "Human" not in (msg.read_by or []):
            return True
    return False


# --- Filters ---
col_filter1, col_filter2 = st.columns(2)
with col_filter1:
    participant_names = ["All", "Human"]
    if _being_name:
        participant_names.append(_being_name)
    display_names = ["All", _user_display_name]
    if _being_name:
        display_names.append(_display_name(_being_name))
    filter_display = st.selectbox("Filter by participant", display_names)
with col_filter2:
    filter_status = st.selectbox("Filter by status", ["active", "dormant", "all"])

# Apply filters — map display name back to internal
_filter_map = dict(zip(display_names, participant_names))
filter_participant = _filter_map.get(filter_display, filter_display)
participant = None if filter_participant == "All" else filter_participant
status = None if filter_status == "all" else filter_status
threads = thread_store.list_threads(participant=participant, status=status)

# --- Two-column layout: thread list | selected thread ---
list_col, thread_col = st.columns([2, 5])

with list_col:
    st.subheader(f"Threads ({len(threads)})")

    if not threads:
        st.info("No threads found.")
    else:
        thread_container = st.container(height=500)
        with thread_container:
            for thread in threads:
                unread = has_unread(thread)
                dot = "🟢 " if unread else ""
                msg_count = len(thread.messages)
                participants_str = ", ".join(
                    _display_name(p) for p in thread.participants
                )
                time_str = format_timestamp(thread.last_activity)

                is_selected = st.session_state.selected_thread_id == thread.id

                if st.button(
                    f"{dot}{_display_subject(thread.subject)}\n{participants_str} · {msg_count} msgs · {time_str}",
                    key=f"thread_{thread.id}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    st.session_state.selected_thread_id = thread.id
                    st.rerun()

with thread_col:
    selected_id = st.session_state.selected_thread_id
    selected_thread = None

    if selected_id:
        for t in threads:
            if t.id == selected_id:
                selected_thread = t
                break
        if selected_thread is None:
            selected_thread = thread_store.get_thread(selected_id)

    if selected_thread is None:
        st.info("Select a thread from the list.")
    else:
        thread = selected_thread
        status_icon = {"active": "🟢", "dormant": "🟡", "closed": "⚫"}.get(
            thread.status, "⚪"
        )
        st.subheader(f"{status_icon} {_display_subject(thread.subject)}")
        st.caption(
            f"{', '.join(_display_name(p) for p in thread.participants)} · {thread.status} · last activity {format_timestamp(thread.last_activity)}"
        )

        if thread.summary:
            st.caption(f"Summary: {thread.summary}")

        # --- Message display with pagination ---
        messages = thread.messages
        total = len(messages)
        show_all = thread.id in st.session_state.show_all_messages

        if total > PREVIEW_COUNT and not show_all:
            hidden = total - PREVIEW_COUNT
            if st.button(
                f"Load {hidden} earlier message{'s' if hidden != 1 else ''}",
                key=f"loadmore_{thread.id}",
            ):
                st.session_state.show_all_messages.add(thread.id)
                st.rerun()
            visible = messages[-PREVIEW_COUNT:]
        else:
            visible = messages

        msg_container = st.container(height=400)
        with msg_container:
            for msg in visible:
                is_human = msg.author == "Human"
                avatar = "👤" if is_human else "🤖"
                with st.chat_message(
                    "user" if is_human else "assistant", avatar=avatar
                ):
                    st.caption(
                        f"**{_display_name(msg.author)}** — {format_timestamp_short(msg.timestamp)}"
                    )
                    st.write(msg.content)

        # Mark as read when viewing
        if has_unread(thread):
            thread_store.mark_thread_read(thread.id, "Human")

        # --- Reply form ---
        st.divider()
        reply_key = f"reply_{thread.id}"

        with st.form(reply_key):
            reply_text = st.text_area(
                "Message", height=80, key=f"replytext_{thread.id}"
            )
            submitted = st.form_submit_button("Send")

            if submitted and reply_text.strip():
                from core.threads import ThreadMessage

                thread_store.append_message(
                    thread.id,
                    ThreadMessage(
                        author="Human",
                        content=reply_text.strip(),
                        timestamp=datetime.now().isoformat(),
                    ),
                )
                thread_store.mark_thread_read(thread.id, "Human")
                st.success("Message sent.")
                st.rerun()

# --- Compose New Thread ---
st.divider()
st.subheader("New Thread")

all_participants = ["Human"]
if _being_name:
    all_participants.append(_being_name)
# Display names for the UI
_participant_display = {p: _display_name(p) for p in all_participants}

with st.form("compose_thread"):
    col1, col2 = st.columns(2)
    with col1:
        display_options = [_participant_display[p] for p in all_participants]
        selected_display = st.multiselect(
            "Participants",
            display_options,
            default=display_options,
        )
    with col2:
        subject = st.text_input("Subject")
    initial_message = st.text_area("Message", height=100)
    compose_as = st.selectbox("Send as", [_user_display_name])
    submitted = st.form_submit_button("Start Thread")

    if submitted:
        # Map display names back to internal names
        _display_to_internal = {v: k for k, v in _participant_display.items()}
        selected_participants = [
            _display_to_internal.get(d, d) for d in selected_display
        ]
        if len(selected_participants) < 2:
            st.error("A thread needs at least 2 participants.")
        elif not subject.strip():
            st.error("Subject is required.")
        elif not initial_message.strip():
            st.error("Message is required.")
        else:
            from core.threads import ThreadMessage

            msg = ThreadMessage(
                author="Human",
                content=initial_message.strip(),
                timestamp=datetime.now().isoformat(),
            )
            new_thread = thread_store.create_thread(
                participants=selected_participants,
                subject=subject.strip(),
                initial_message=msg,
            )
            st.session_state.selected_thread_id = new_thread.id
            st.success(f"Thread '{subject}' created!")
            st.rerun()
