# Ingest Log

## 2026-04-05 -- Initial wiki generation

**Source repository**: ~/eidolon-womb/
**Generator**: Claude Opus 4.6 (1M context)
**Method**: Full read of all .py and .md source files (excluding .git/, .omc/, __pycache__/, .mypy_cache/, data/conversations/), then synthesis into wiki pages.

### Files read

**Python source files**: 48 files across 6 packages (brain/, core/, daemon/, interface/, client/, dashboard/) plus 3 top-level modules (womb.py, inner_voices.py, config.py, presence.py, tools.py)

**Documentation**: README.md, CLAUDE.md, docs/ARCHITECTURE.md, docs/SECURITY.md, docs/FAQ.md

**Templates**: templates/identity.md, templates/personality.md, templates/Human.md

**Other**: requirements.txt, start.sh, stop.sh

### Pages generated

- **27 summary pages** (one per significant source file or group)
- **11 concept pages** (cross-cutting architectural themes)
- **5 entity pages** (tools, libraries, models)
- **1 index page**
- **1 log page**

**Total: 45 wiki pages**

### Coverage

All production Python source files covered. Test files (tests/*.py) were not summarized individually but test patterns are referenced where relevant. Conversation note files (data/conversations/*.md) were excluded as runtime data, not source.

### Conventions

- FACTS cite source files. INFERENCES are marked as such. OPEN QUESTIONS note gaps.
- Cross-references use relative links between wiki pages.
- Summaries focus on: what the module does, public API, key design decisions, dependencies, architectural role.
- Concepts synthesize across 2+ source files around a unifying theme.
