# nomic-embed-text

Embedding model for semantic memory retrieval.

## Role in Eidolon Womb

Generates vector embeddings for memory chunks and queries, enabling semantic (meaning-based) search alongside BM25 keyword search.

## Usage

- **Memory index**: Embeds all memory chunks (consolidated memories, session notes/summaries, facts) for similarity search. Cached in SQLite. (Source: `brain/retrieval.py:117-119`)
- **Hot voice similarity**: Embeds recent assistant replies and current reply to detect semantic similarity loops during chat. (Source: `womb.py:384-386`)
- **Similarity mode**: Optional semantic mode for hot voice idle detection (default is Jaccard word overlap). (Source: `inner_voices.py:153-165`)

## Configuration

- Model name: `nomic-embed-text` (Source: `core/config.py:159`)
- Max input: 8,192 tokens (truncated to 8,000 chars as safety net). (Source: `brain/retrieval.py:15`)
- Blend weights: 0.7 vector + 0.3 BM25 in retrieval. (Source: `core/config.py:161`)

## Caching

Embeddings cached in `data/memory_index.db` (SQLite), keyed by SHA-256 of content. Stale entries cleaned on index rebuild. Cache survives daemon restarts. (Source: `brain/retrieval.py:27-34, 84-95`)
