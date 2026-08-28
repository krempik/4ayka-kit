"""gen: materialize a spec into a ready-to-run FastAPI application.

Writes every generated file to <target>/; existing files are overwritten
(regenerated) — user edits survive only if you keep them out of app/ or
re-apply after regeneration.
"""
import os
from pathlib import Path
from typing import List

from . import snippets
from .spec import ProjectSpec

APP_FILES = [
    ("app/__init__.py", lambda spec: snippets.package_init()),
    ("app/config.py", snippets.config_code),
    ("app/database.py", snippets.database_code),
    ("app/models.py", snippets.models_code),
    ("app/schemas.py", snippets.schemas_code),
    ("app/routes.py", snippets.routes_code),
    ("app/main.py", snippets.main_code),
    ("run.py", snippets.run_py_code),
    ("run.bat", lambda s: snippets.RUN_BAT),
    ("requirements.txt", lambda s: snippets.REQUIREMENTS),
    (".gitignore", lambda s: snippets.GITIGNORE),
    ("README.md", snippets.readme_code),
    ("tests/test_api.py", snippets.tests_code),
    (".github/workflows/ci.yml", snippets.ci_code),
]


def generate(spec: ProjectSpec, target: str | os.PathLike) -> List[str]:
    """Writes all generated files under target and returns the relative paths."""
    target = Path(target)
    written = []
    for rel, fn in APP_FILES:
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fn(spec), encoding="utf-8", newline="\n")
        written.append(rel)
    return written


__all__ = ["generate", "APP_FILES"]