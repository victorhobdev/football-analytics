from __future__ import annotations

from pathlib import Path


def resolve_repo_root() -> Path:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        if (parent / "README.md").is_file() and (parent / "api").is_dir():
            return parent
    raise RuntimeError("Repository root not found")
