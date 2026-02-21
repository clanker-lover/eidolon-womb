"""Agora — public forum wall."""

import os
import streamlit as st
from utils import (
    load_registry, load_agora, get_project_root,
    format_timestamp, list_files_in, read_file_safe,
)

st.header("Agora")

registry = load_registry()
beings = registry.list_beings()
agora = load_agora()

# --- Current Wall ---
st.subheader("Wall")

posts = agora.read_agora()

if not posts:
    st.info("The agora is quiet. No posts yet.")
else:
    for post in posts:
        st.markdown(
            f"**{post.being_name}** &mdash; {format_timestamp(post.posted_at)}"
        )
        st.write(post.content)
        st.divider()

# --- Compose ---
st.subheader("New Post")

if not beings:
    st.info("No beings registered to post.")
else:
    with st.form("agora_post_form"):
        being_names = [b.name for b in beings]
        poster_name = st.selectbox("Post as", being_names)
        content = st.text_area("Content", height=100)
        submitted = st.form_submit_button("Post")

        if submitted:
            if not content.strip():
                st.error("Post cannot be empty.")
            else:
                poster = next(b for b in beings if b.name == poster_name)
                agora.post_to_agora(poster.name, poster.id, content.strip())
                st.success("Posted to the agora.")
                st.rerun()

# --- Archives ---
st.divider()
st.subheader("Archives")

root = get_project_root()
archive_dir = os.path.join(root, "data", "agora", "archive")
archives = list_files_in(archive_dir)

if not archives:
    st.info("No archived weeks yet.")
else:
    for fname in sorted(archives, reverse=True):
        with st.expander(fname):
            path = os.path.join(archive_dir, fname)
            st.markdown(read_file_safe(path))
