# Ollama

Local LLM inference server used for all generation and embedding.

## Role in Eidolon Womb

Ollama is the inference backend for the entire system. All LLM calls go through the `ollama` Python library.

## Usage

- **Chat generation**: `ollama.chat()` for thought cycles, chat responses, inner voice generation, fact extraction, session summarization, consolidation, and relationship updates. (Source: `womb.py:260-271`, `inner_voices.py:179-194`, `brain/memory.py:48-54`)
- **Embeddings**: `ollama.embed()` for vector similarity in hybrid memory retrieval and hot voice similarity detection. Model: `nomic-embed-text`. (Source: `brain/retrieval.py:117-119`, `womb.py:384-386`)
- **Binary gate**: `ollama.generate()` for single-token yes/no decisions in the intent system. (Source: `brain/intent.py:47-53`)
- **Health probe**: `ollama.list()` at startup to verify availability. (Source: `daemon/lifecycle.py:217-219`)

## Models Required

- `llama3.2:3b` -- Primary language model (configurable via `MODEL_NAME`)
- `nomic-embed-text` -- Embedding model for memory retrieval

## Configuration

- Host: defaults to localhost (Ollama's default)
- Temperature: 0.7 (general), 0.0 (fact extraction, binary gate), 0.1 (cold voice), 0.95 (hot voice), 0.3 (notes), 0.5 (consolidation)
- Context window: 16,384 tokens

## Source

https://ollama.com -- Local LLM server. Python library: `ollama>=0.4.0` (Source: `requirements.txt:2`)
