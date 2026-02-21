import glob
import hashlib
import json
import math
import os
import sqlite3

import ollama
from rank_bm25 import BM25Okapi

from config import RETRIEVAL_BLEND_WEIGHTS


class MemoryIndex:
    # nomic-embed-text has an 8192-token context; truncate as a safety net.
    _EMBED_MAX_CHARS = 8000

    def __init__(self, data_dir: str, embedding_model: str = "nomic-embed-text"):
        self._data_dir = data_dir
        self._embedding_model = embedding_model
        self._chunks: list[dict] = []
        self._bm25: BM25Okapi | None = None
        self._embedding_available = True
        self._db_path = os.path.join(data_dir, "memory_index.db")
        self._init_cache()

    def _init_cache(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(chunk_hash TEXT PRIMARY KEY, embedding TEXT NOT NULL)"
        )
        conn.commit()
        conn.close()

    def rebuild(self) -> None:
        self._chunks = []

        # 1. Session summaries
        pattern = os.path.join(self._data_dir, "conversations", "*_summary.md")
        for path in glob.glob(pattern):
            with open(path, "r") as f:
                text = f.read().strip()
            if text:
                self._chunks.append({"text": text, "source": os.path.basename(path)})

        # 2. Facts
        facts_path = os.path.join(self._data_dir, "memories", "facts.md")
        if os.path.exists(facts_path):
            with open(facts_path, "r") as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        self._chunks.append({"text": line, "source": f"facts.md:{i}"})

        # 3. Session notes
        pattern = os.path.join(self._data_dir, "conversations", "*_notes.md")
        for path in glob.glob(pattern):
            with open(path, "r") as f:
                text = f.read().strip()
            if text:
                self._chunks.append({"text": text, "source": os.path.basename(path)})

        # 4. Consolidated memories
        pattern = os.path.join(self._data_dir, "memories", "consolidated", "*.md")
        for path in glob.glob(pattern):
            with open(path, "r") as f:
                text = f.read().strip()
            if text:
                self._chunks.append(
                    {"text": text, "source": f"consolidated/{os.path.basename(path)}"}
                )

        # Build BM25 index
        if self._chunks:
            tokenized = [c["text"].lower().split() for c in self._chunks]
            self._bm25 = BM25Okapi(tokenized)
        else:
            self._bm25 = None

        # Clean stale cache entries
        self._clean_cache()

    def _clean_cache(self) -> None:
        current_hashes = {self._hash(c["text"]) for c in self._chunks}
        conn = sqlite3.connect(self._db_path)
        stored = {row[0] for row in conn.execute("SELECT chunk_hash FROM cache")}
        stale = stored - current_hashes
        if stale:
            conn.executemany(
                "DELETE FROM cache WHERE chunk_hash = ?",
                [(h,) for h in stale],
            )
            conn.commit()
        conn.close()

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _get_embedding(self, text: str) -> list[float] | None:
        chunk_hash = self._hash(text)

        # Check cache
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT embedding FROM cache WHERE chunk_hash = ?", (chunk_hash,)
        ).fetchone()
        if row:
            conn.close()
            return json.loads(row[0])

        # Truncate to fit embedding model context window
        embed_text = text[: self._EMBED_MAX_CHARS]

        # Compute via ollama
        try:
            response = ollama.embed(model=self._embedding_model, input=embed_text)
            embedding = response["embeddings"][0]
        except Exception as e:
            # Context-length errors are per-chunk, not model-level failures
            if "context length" not in str(e):
                self._embedding_available = False
            conn.close()
            return None

        # Store in cache (keyed on full text hash, not truncated)
        conn.execute(
            "INSERT OR REPLACE INTO cache (chunk_hash, embedding) VALUES (?, ?)",
            (chunk_hash, json.dumps(embedding)),
        )
        conn.commit()
        conn.close()
        return embedding

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self._chunks or not self._bm25:
            return []

        n = len(self._chunks)
        vector_weight, bm25_weight = RETRIEVAL_BLEND_WEIGHTS

        # BM25 scores
        tokenized_query = query.lower().split()
        bm25_raw = self._bm25.get_scores(tokenized_query)
        bm25_max = max(bm25_raw) if max(bm25_raw) > 0 else 1.0
        bm25_norm = [s / bm25_max for s in bm25_raw]

        # Vector scores
        vector_norm = [0.0] * n
        if self._embedding_available:
            query_emb = self._get_embedding(query)
            if query_emb:
                raw_scores = []
                for chunk in self._chunks:
                    emb = self._get_embedding(chunk["text"])
                    if emb:
                        raw_scores.append(self._cosine_similarity(query_emb, emb))
                    else:
                        raw_scores.append(0.0)
                v_max = max(raw_scores) if max(raw_scores) > 0 else 1.0
                vector_norm = [s / v_max for s in raw_scores]
            else:
                # Embedding failed for query — fall back to BM25 only
                vector_weight, bm25_weight = 0.0, 1.0
        else:
            vector_weight, bm25_weight = 0.0, 1.0

        # Blend
        final_scores = [
            vector_weight * vector_norm[i] + bm25_weight * bm25_norm[i]
            for i in range(n)
        ]

        # Rank and filter
        scored = [
            {
                "text": self._chunks[i]["text"],
                "source": self._chunks[i]["source"],
                "score": final_scores[i],
            }
            for i in range(n)
            if final_scores[i] > 0
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
