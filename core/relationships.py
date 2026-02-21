"""Relationship files — per-being markdown notes about other participants."""

import os

_TEMPLATE = """\
# {name}
## Facts
{facts}
## Our History

## My Sense of Them
"""


def _rel_dir(project_root: str, memory_path: str) -> str:
    return os.path.join(project_root, memory_path, "relationships")


def _rel_path(project_root: str, memory_path: str, other_name: str) -> str:
    return os.path.join(_rel_dir(project_root, memory_path), f"{other_name}.md")


def load_relationship(project_root: str, memory_path: str, other_name: str) -> str:
    path = _rel_path(project_root, memory_path, other_name)
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()


def save_relationship(
    project_root: str, memory_path: str, other_name: str, content: str
) -> None:
    directory = _rel_dir(project_root, memory_path)
    os.makedirs(directory, exist_ok=True)
    path = _rel_path(project_root, memory_path, other_name)
    with open(path, "w") as f:
        f.write(content)


def ensure_relationship(
    project_root: str,
    memory_path: str,
    other_name: str,
    seed_facts: list[str] | None = None,
) -> str:
    path = _rel_path(project_root, memory_path, other_name)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    facts_str = (
        "\n".join(f"- {f}" for f in seed_facts) if seed_facts else "- (none yet)"
    )
    content = _TEMPLATE.format(name=other_name, facts=facts_str)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return content


def list_relationships(project_root: str, memory_path: str) -> list[str]:
    directory = _rel_dir(project_root, memory_path)
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.splitext(f)[0] for f in os.listdir(directory) if f.endswith(".md")
    )
