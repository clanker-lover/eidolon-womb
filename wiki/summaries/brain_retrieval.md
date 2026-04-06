# brain/retrieval.py

Hybrid memory retrieval -- BM25 keyword search blended with vector embeddings.

## What It Does

`MemoryIndex` builds and queries an index over all memory sources: consolidated memories, session summaries, session notes, and learned facts. Retrieval is called every thought cycle and every chat turn.

## Key Class: MemoryIndex

- **`__init__(data_dir, embedding_model)`** -- Initializes SQLite cache at `data_dir/memory_index.db` for embedding persistence. (Source: `brain/retrieval.py:18-25`)
- **`rebuild()`** -- Scans four memory sources (summaries, facts, notes, consolidated) and builds BM25 index. Cleans stale cache entries. (Source: `brain/retrieval.py:36-83`)
- **`search(query, top_k)`** -- Blended search: BM25 scores normalized to [0,1], vector cosine similarity normalized to [0,1], then weighted blend (default 0.7 vector, 0.3 BM25). Falls back to BM25-only if embeddings unavailable. Returns list of `{text, source, score}`. (Source: `brain/retrieval.py:145-195`)

## Embedding Cache

Embeddings computed via Ollama's `nomic-embed-text` model. Cached in SQLite keyed by SHA-256 hash of content. Input truncated to 8000 chars (model context limit). Cache survives restarts and is cleaned of stale entries on rebuild. (Source: `brain/retrieval.py:101-134`)

## Memory Sources

1. `conversations/*_summary.md` -- Session summaries
2. `memories/facts.md` -- Learned facts (line by line)
3. `conversations/*_notes.md` -- Private reflection notes
4. `memories/consolidated/*.md` -- Dream-processed long-term memories

## Dependencies

`ollama`, `rank_bm25` (BM25Okapi), `sqlite3`, `config` (RETRIEVAL_BLEND_WEIGHTS)

See also: [concept: memory-system](../concepts/memory_system.md), [brain_memory](brain_memory.md), [brain_consolidation](brain_consolidation.md)
