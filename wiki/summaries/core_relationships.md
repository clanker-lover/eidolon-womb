# core/relationships.py

Per-being markdown relationship files.

## What It Does

CRUD operations for relationship files -- markdown documents that track what the being knows about each participant (Human, other beings).

## Key Functions

- **`load_relationship(project_root, memory_path, other_name)`** -- Reads `{memory_path}/relationships/{other_name}.md`. (Source: `core/relationships.py:23-27`)
- **`save_relationship(project_root, memory_path, other_name, content)`** -- Writes updated relationship file. (Source: `core/relationships.py:30-37`)
- **`ensure_relationship(project_root, memory_path, other_name, seed_facts)`** -- Creates relationship file from template if it doesn't exist. Template includes Facts, Our History, and My Sense of Them sections. (Source: `core/relationships.py:40-58`)
- **`list_relationships(project_root, memory_path)`** -- Lists all relationship file names (without .md extension). (Source: `core/relationships.py:61-67`)

## Template

```markdown
# {name}
## Facts
{facts}
## Our History
## My Sense of Them
```

## Dependencies

`os`

See also: [brain_consolidation](brain_consolidation.md) (updates relationships during sleep)
