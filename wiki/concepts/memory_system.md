# Memory System

How the being remembers: hybrid retrieval, fact extraction, and dream consolidation.

## FACTS

- Memory retrieval blends BM25 keyword search with vector embeddings (nomic-embed-text via Ollama). Default weights: 0.7 vector, 0.3 BM25. (Source: `brain/retrieval.py:151`, `core/config.py:161`)
- Embeddings are cached in SQLite (`memory_index.db`) keyed by SHA-256 content hash. Cache survives restarts. (Source: `brain/retrieval.py:97-134`)
- Four memory sources: consolidated memories, session summaries, session notes, learned facts. (Source: `brain/retrieval.py:36-78`)
- Facts are extracted from user messages at temperature 0.0 via a specific extraction prompt. Deduplication uses bidirectional substring matching. Facts are date-stamped. (Source: `brain/memory.py:130-195`)
- Session summaries (2-3 sentences, being's perspective) and private reflection notes are generated at session end. (Source: `brain/memory.py:29-117`)
- Sleep consolidation distills live thoughts + unconsolidated files into long-term memory. Output saved to `memories/consolidated/{timestamp}.md`. Source files archived. (Source: `brain/consolidation.py:63-156`)
- Partial consolidation during naps: oldest portion (ratio-based) consolidated, recent kept in memory. (Source: `brain/consolidation.py:159-212`)
- Retrieval is called every thought cycle (step 2) and every chat turn. Top K = 3 by default. (Source: `core/config.py:160`, `brain/cycle.py:140-150`)

## INFERENCES

- The "hippocampus-to-neocortex" metaphor (consolidation module docstring) maps sleep consolidation to biological memory formation. Recent experiences (hippocampus/session notes) are distilled into long-term storage (neocortex/consolidated memories).
- The consolidation prompt is deliberately journalistic ("What won't let go?") rather than analytical, producing personal memories rather than summaries.

## OPEN QUESTIONS

- How well does the deduplication work in practice? Substring matching after date stripping seems brittle for paraphrased facts.
- With default RETRIEVAL_TOP_K=3, does the being have enough associative context? Could higher K improve coherence?

## Cross-References

- [brain_retrieval](../summaries/brain_retrieval.md) -- Hybrid search
- [brain_memory](../summaries/brain_memory.md) -- Fact extraction
- [brain_consolidation](../summaries/brain_consolidation.md) -- Dream processing
- [sleep-and-dreaming](sleep_and_dreaming.md) -- When consolidation runs
- [context-priority-system](context_priority_system.md) -- How memories enter context
