# brain/identity.py

File loaders for being identity, personality, and human relationship data.

## What It Does

Simple file I/O layer that reads the being's core definition files from its memory root directory.

## Key Functions

- **`load_identity(memory_root)`** -- Reads `{memory_root}/identity.md`. (Source: `brain/identity.py:15-17`)
- **`load_personality(memory_root)`** -- Reads `{memory_root}/personality.md`. (Source: `brain/identity.py:20-22`)
- **`load_human_facts(memory_root)`** -- Reads `{memory_root}/Human.md`, splits by newlines, strips whitespace. Returns list of fact strings. (Source: `brain/identity.py:25-32`)
- **`load_file(filepath)`** -- Generic file reader with `FileNotFoundError` handling. (Source: `brain/identity.py:5-10`)

## Dependencies

`config` (IDENTITY_FILE, PERSONALITY_FILE, HUMAN_FILE)

## Architectural Role

Thin file I/O layer. The actual identity and personality content lives in markdown files under `data/` and is managed by the user (initial setup) and the consolidation system (ongoing evolution). The being's name is parsed from the first line of `identity.md` at startup.

See also: [concept: identity-and-sovereignty](../concepts/identity_and_sovereignty.md)
