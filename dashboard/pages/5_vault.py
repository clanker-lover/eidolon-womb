"""Vault — historical data browser."""

import os
import streamlit as st
from utils import get_project_root, read_file_safe

st.header("Vault")

root = get_project_root()
data_dir = os.path.join(root, "data")

# --- Search ---
search = st.text_input("Filter files by name", placeholder="e.g. brandon, identity, facts")

# --- Directory browser ---
SECTIONS = [
    ("Identity & Personality", "", ["identity.md", "personality.md", "brandon.md"]),
    ("Conversations", "conversations", None),
    ("Archived Conversations", os.path.join("conversations", "archived"), None),
    ("Memories", "memories", None),
    ("Consolidated Memories", os.path.join("memories", "consolidated"), None),
    ("Logs", "logs", None),
    ("Agora", "agora", None),
]

for section_name, subdir, explicit_files in SECTIONS:
    full_dir = os.path.join(data_dir, subdir) if subdir else data_dir

    if explicit_files:
        files = [f for f in explicit_files if os.path.isfile(os.path.join(full_dir, f))]
    else:
        if not os.path.isdir(full_dir):
            continue
        files = [
            f for f in sorted(os.listdir(full_dir), reverse=True)
            if os.path.isfile(os.path.join(full_dir, f))
        ]

    # Apply search filter
    if search:
        files = [f for f in files if search.lower() in f.lower()]

    if not files:
        continue

    st.subheader(section_name)
    st.caption(f"{len(files)} file{'s' if len(files) != 1 else ''}")

    # Show files in a compact list with expand-to-view
    for fname in files:
        fpath = os.path.join(full_dir, fname)
        size = os.path.getsize(fpath)
        size_str = f"{size:,} bytes" if size < 10240 else f"{size / 1024:.1f} KB"
        label = f"{fname} ({size_str})"

        with st.expander(label):
            content = read_file_safe(fpath)
            if fname.endswith((".md", ".txt", ".log")):
                st.markdown(content)
            elif fname.endswith(".json"):
                st.code(content, language="json")
            else:
                st.code(content)
