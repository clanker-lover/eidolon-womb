import os
import sys
import unittest
from unittest.mock import patch
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from brain.retrieval import MemoryIndex  # noqa: E402
from brain.memory import generate_eidolon_notes  # noqa: E402
from brain.context import assemble_messages  # noqa: E402


def _make_data_dir(tmpdir):
    """Create a temp data directory with sample memory files."""
    data_dir = os.path.join(tmpdir, "data")
    conv_dir = os.path.join(data_dir, "conversations")
    mem_dir = os.path.join(data_dir, "memories")
    os.makedirs(conv_dir)
    os.makedirs(mem_dir)

    # Session summaries
    summaries = {
        "2026-02-10_1400_summary.md": (
            "I talked with Human about Stephanie and how she's been feeling lately. "
            "He seemed worried about her health."
        ),
        "2026-02-11_0900_summary.md": (
            "Human asked me about deploying models on the Jetson Orin Nano. "
            "We discussed hardware constraints and quantization."
        ),
        "2026-02-12_1000_summary.md": (
            "We talked about naming — Human is thinking about what to call me. "
            "He considered several options."
        ),
        "2026-02-13_1100_summary.md": (
            "Human opened up about his agoraphobia and how it affects his daily life. "
            "I tried to be supportive without overstepping."
        ),
        "2026-02-14_1500_summary.md": (
            "We talked about Human's hobby of building electronics projects. "
            "He's working on a custom PCB design."
        ),
    }
    for fname, content in summaries.items():
        with open(os.path.join(conv_dir, fname), "w") as f:
            f.write(content)

    # Facts
    facts = [
        "[2026-02-10] Human's girlfriend is named Stephanie",
        "[2026-02-10] Human is 31 years old",
        "[2026-02-11] Human has a Jetson Orin Nano",
        "[2026-02-12] Human has agoraphobia",
        "[2026-02-13] Human enjoys building electronics",
    ]
    with open(os.path.join(mem_dir, "facts.md"), "w") as f:
        f.write("\n".join(facts) + "\n")

    # Eidolon notes
    notes = {
        "2026-02-10_1400_notes.md": (
            "Human seems really attached to Stephanie. I should remember to ask about her."
        ),
        "2026-02-13_1100_notes.md": (
            "The agoraphobia conversation felt important. He doesn't talk about it easily."
        ),
    }
    for fname, content in notes.items():
        with open(os.path.join(conv_dir, fname), "w") as f:
            f.write(content)

    return data_dir


class TestChunkParsing(unittest.TestCase):
    """Verify rebuild() collects correct chunks from all sources."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.data_dir = _make_data_dir(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_rebuild_collects_all_chunks(self):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        # 5 summaries + 5 facts + 2 notes = 12
        self.assertEqual(len(idx._chunks), 12)

    def test_summary_chunks_present(self):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        sources = [c["source"] for c in idx._chunks]
        summary_sources = [s for s in sources if s.endswith("_summary.md")]
        self.assertEqual(len(summary_sources), 5)

    def test_fact_chunks_present(self):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        sources = [c["source"] for c in idx._chunks]
        fact_sources = [s for s in sources if s.startswith("facts.md:")]
        self.assertEqual(len(fact_sources), 5)

    def test_notes_chunks_present(self):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        sources = [c["source"] for c in idx._chunks]
        notes_sources = [s for s in sources if s.endswith("_notes.md")]
        self.assertEqual(len(notes_sources), 2)

    def test_empty_files_skipped(self):
        empty_path = os.path.join(self.data_dir, "conversations", "2026-02-15_0800_summary.md")
        with open(empty_path, "w") as f:
            f.write("")
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        self.assertEqual(len(idx._chunks), 12)


class TestBM25Search(unittest.TestCase):
    """Test BM25-only search (embedding disabled)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.data_dir = _make_data_dir(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("brain.retrieval.MemoryIndex._get_embedding", return_value=None)
    def test_stephanie_query_ranks_stephanie_first(self, mock_embed):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        idx._embedding_available = False
        results = idx.search("How is Stephanie?")
        self.assertTrue(len(results) > 0)
        self.assertIn("Stephanie", results[0]["text"])

    @patch("brain.retrieval.MemoryIndex._get_embedding", return_value=None)
    def test_jetson_query_ranks_hardware_first(self, mock_embed):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        idx._embedding_available = False
        results = idx.search("Jetson deployment")
        self.assertTrue(len(results) > 0)
        self.assertIn("Jetson", results[0]["text"])

    @patch("brain.retrieval.MemoryIndex._get_embedding", return_value=None)
    def test_exact_keyword_scores_well(self, mock_embed):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        idx._embedding_available = False
        results = idx.search("agoraphobia")
        self.assertTrue(len(results) > 0)
        found_agoraphobia = any("agoraphobia" in r["text"].lower() for r in results)
        self.assertTrue(found_agoraphobia)

    @patch("brain.retrieval.MemoryIndex._get_embedding", return_value=None)
    def test_returns_at_most_top_k(self, mock_embed):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        idx._embedding_available = False
        results = idx.search("Human", top_k=2)
        self.assertLessEqual(len(results), 2)


class TestHybridSearch(unittest.TestCase):
    """Test hybrid blending with deterministic fake vectors."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.data_dir = _make_data_dir(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _fake_embedding(self, text):
        """Deterministic fake embedding: hash text to produce a 384-dim vector."""
        import hashlib
        h = hashlib.sha256(text.encode()).hexdigest()
        vec = []
        for i in range(0, min(len(h), 384 * 2), 2):
            vec.append(int(h[i:i+2], 16) / 255.0)
        # Pad to 384 dims
        while len(vec) < 384:
            vec.append(0.5)
        return vec

    @patch("brain.retrieval.MemoryIndex._get_embedding")
    def test_hybrid_returns_results(self, mock_embed):
        mock_embed.side_effect = self._fake_embedding
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        results = idx.search("Stephanie")
        self.assertTrue(len(results) > 0)
        # All scores should be between 0 and 1
        for r in results:
            self.assertGreaterEqual(r["score"], 0)
            self.assertLessEqual(r["score"], 1.01)  # small float tolerance

    @patch("brain.retrieval.MemoryIndex._get_embedding")
    def test_hybrid_scores_have_both_components(self, mock_embed):
        mock_embed.side_effect = self._fake_embedding
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        results = idx.search("electronics hobby PCB")
        self.assertTrue(len(results) > 0)
        # Top result should have score > 0 (both BM25 and vector contribute)
        self.assertGreater(results[0]["score"], 0)


class TestGracefulDegradation(unittest.TestCase):
    """Verify search works when ollama.embed fails."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.data_dir = _make_data_dir(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("brain.retrieval.MemoryIndex._get_embedding", side_effect=Exception("ollama down"))
    def test_search_falls_back_to_bm25(self, mock_embed):
        idx = MemoryIndex(self.data_dir)
        idx.rebuild()
        idx._embedding_available = False
        results = idx.search("Stephanie")
        self.assertTrue(len(results) > 0)
        self.assertIn("Stephanie", results[0]["text"])

    def test_search_on_empty_index(self):
        empty_dir = os.path.join(self.tmpdir, "empty_data")
        os.makedirs(os.path.join(empty_dir, "conversations"), exist_ok=True)
        os.makedirs(os.path.join(empty_dir, "memories"), exist_ok=True)
        idx = MemoryIndex(empty_dir)
        idx.rebuild()
        results = idx.search("anything")
        self.assertEqual(results, [])


class TestEmbeddingCache(unittest.TestCase):
    """Verify SQLite cache creation and hit behavior."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.data_dir = _make_data_dir(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_cache_db_created(self):
        MemoryIndex(self.data_dir)  # side effect: creates db
        db_path = os.path.join(self.data_dir, "memory_index.db")
        self.assertTrue(os.path.exists(db_path))

    @patch("brain.retrieval.ollama")
    def test_cache_avoids_re_embedding(self, mock_ollama_mod):
        fake_vec = [0.1] * 384
        mock_ollama_mod.embed.return_value = {"embeddings": [fake_vec]}

        idx = MemoryIndex(self.data_dir)
        idx.rebuild()

        # First search — embeds all chunks + query
        idx.search("Stephanie")
        first_call_count = mock_ollama_mod.embed.call_count

        # Second search with same query — query embedding cached, chunks cached
        idx.search("Stephanie")
        second_call_count = mock_ollama_mod.embed.call_count

        # Should not have re-embedded chunks
        self.assertEqual(first_call_count, second_call_count)


class TestEidolonNotes(unittest.TestCase):
    """Verify generate_eidolon_notes creates _notes.md files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.session_path = os.path.join(self.tmpdir, "2026-02-15_1000.md")
        with open(self.session_path, "w") as f:
            f.write("# Session 2026-02-15_1000\n\n")
            f.write("**You:** How are you doing today?\n\n")
            f.write("**Eidolon:** I'm here with you.\n\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("brain.memory.ollama.chat")
    def test_notes_file_created(self, mock_chat):
        mock_chat.return_value = {"message": {"content": "Human seemed reflective today. I want to remember this."}}
        result = generate_eidolon_notes(self.session_path, "test-model", 2048)
        notes_path = self.session_path.replace(".md", "_notes.md")
        self.assertTrue(os.path.exists(notes_path))
        self.assertIsNotNone(result)

    @patch("brain.memory.ollama.chat")
    def test_notes_content_nonempty(self, mock_chat):
        mock_chat.return_value = {"message": {"content": "Something meaningful."}}
        generate_eidolon_notes(self.session_path, "test-model", 2048)
        notes_path = self.session_path.replace(".md", "_notes.md")
        with open(notes_path) as f:
            content = f.read()
        self.assertTrue(len(content.strip()) > 0)

    @patch("brain.memory.ollama.chat")
    def test_temperature_is_0_3(self, mock_chat):
        mock_chat.return_value = {"message": {"content": "Reflection text."}}
        generate_eidolon_notes(self.session_path, "test-model", 2048)
        call_args = mock_chat.call_args
        options = call_args[1]["options"]
        self.assertAlmostEqual(options["temperature"], 0.3)

    @patch("brain.memory.ollama.chat")
    def test_skips_empty_session(self, mock_chat):
        empty_path = os.path.join(self.tmpdir, "empty.md")
        with open(empty_path, "w") as f:
            f.write("# Session empty\n")
        result = generate_eidolon_notes(empty_path, "test-model", 2048)
        self.assertIsNone(result)
        mock_chat.assert_not_called()

    def test_skips_missing_file(self):
        result = generate_eidolon_notes("/nonexistent/path.md", "test-model", 2048)
        self.assertIsNone(result)


class TestAssembleWithRetrieved(unittest.TestCase):
    """Verify assemble_messages handles retrieved_memories correctly."""

    def test_backward_compatibility(self):
        """Old call signature without retrieved_memories still works."""
        result, _tokens = assemble_messages(
            "perception", "identity", "personality",
            ["fact1"], ["learned1"], [], "hello",
            session_summaries=["summary1"],
        )
        self.assertTrue(len(result) >= 2)

    def test_memory_prefix_in_system(self):
        """retrieved_memories appear with [Memory] prefix."""
        memories = [
            {"text": "Human talked about Stephanie", "source": "test.md", "score": 0.8},
        ]
        result, _tokens = assemble_messages(
            "perception", "identity", "personality",
            [], [], [], "hello",
            retrieved_memories=memories,
        )
        system_content = result[0]["content"]
        self.assertIn("[Memory] Human talked about Stephanie", system_content)

    def test_memories_before_summaries(self):
        """[Memory] block appears before session summaries in system content."""
        memories = [
            {"text": "a retrieved memory", "source": "test.md", "score": 0.8},
        ]
        result, _tokens = assemble_messages(
            "perception", "identity", "personality",
            [], [], [], "hello",
            session_summaries=["[Session old] summary text"],
            retrieved_memories=memories,
        )
        system_content = result[0]["content"]
        mem_pos = system_content.find("[Memory]")
        sess_pos = system_content.find("[Session old]")
        self.assertNotEqual(mem_pos, -1)
        self.assertNotEqual(sess_pos, -1)
        self.assertLess(mem_pos, sess_pos)

    def test_none_retrieved_memories_ok(self):
        """Passing None for retrieved_memories doesn't break anything."""
        result, _tokens = assemble_messages(
            "perception", "identity", "personality",
            [], [], [], "hello",
            retrieved_memories=None,
        )
        self.assertTrue(len(result) >= 2)


if __name__ == "__main__":
    unittest.main()
