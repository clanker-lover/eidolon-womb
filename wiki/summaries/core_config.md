# core/config.py

Central configuration -- all tunable values in one file.

## What It Does

Single source of truth for all configuration constants. No environment variables, no config files -- just Python constants.

## Key Configuration Groups

**Model**: `MODEL_NAME` = "llama3.2:3b", `CONTEXT_WINDOW` = 16384, `TEMPERATURE` = 0.7, `RESPONSE_RESERVE` = 1024, `IDLE_RESPONSE_RESERVE` = 100

**Fatigue thresholds**: `FATIGUE_TIRED` = 0.50, `FATIGUE_VERY_TIRED` = 0.75, `FATIGUE_EXHAUSTED` = 0.85, `FATIGUE_INVOLUNTARY_SLEEP` = 0.92

**Sleep**: `SLEEP_RECOVERY_MAP` maps hours (1/4/6/8/10) to label, consolidation flag, and ratio. `DEFAULT_SLEEP_HOURS` = 6.

**Inner voices**: `COLD_VOICE_TEMPERATURE` = 0.1, `HOT_VOICE_TEMPERATURE` = 0.95, `HOT_VOICE_MIN_STALE_CYCLES` = 10, `HOT_VOICE_SIMILARITY_THRESHOLD` = 0.65

**Retrieval**: `EMBEDDING_MODEL` = "nomic-embed-text", `RETRIEVAL_BLEND_WEIGHTS` = (0.7, 0.3), `RETRIEVAL_TOP_K` = 3

**Prompts**: `MEMORY_EXTRACTION_PROMPT`, `SESSION_SUMMARY_PROMPT`, `EIDOLON_REFLECTION_PROMPT`, `CONSOLIDATION_PROMPT`, `IDLE_FRESH_THOUGHT_PROMPT`, `IDLE_CONTINUATION_PROMPT`

**Weather**: `WEATHER_LAT` = 39.9714, `WEATHER_LON` = -104.8202 (Brighton, CO), `WEATHER_CACHE_SECONDS` = 900

**Pattern lists**: `COLD_VOICE_EXPERIENCE_PATTERNS`, `COLD_VOICE_FABRICATION_PATTERNS`, `COLD_VOICE_SENSORY_PATTERNS`, `KNOWN_BEING_NAMES`

**Daemon**: `DAEMON_PORT` = 7777

## Dependencies

None (leaf module)

## Architectural Role

Configuration hub. Imported by nearly every module. The backward-compat stub at `config.py` re-exports everything via `from core.config import *`.

See also: [config_py](config_py.md)
