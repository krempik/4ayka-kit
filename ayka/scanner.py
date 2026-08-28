"""Project context scanner.

Walks a project (skipping venv/caches/binaries), extracts the surface an AI
agent needs to start working: entry point, framework, how to run, tests,
endpoints, models, env vars, version. Emits either a human-readable structure
report or a compact `--ai` context pack.
"""
import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

SKIP_DIRS = {
    "venv", ".venv", "__pycache__", ".git", ".pytest_cache",
    "node_modules", "dist", "build", "uploads", "data", ".idea", ".vscode",
}
SKIP_EXTS = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".db",
             ".sqlite", ".lock", ".woff", ".woff2", ".ttf", ".mp3", ".mp4",
             ".wav", ".ogg", ".pdf", ".zip", ".exe", ".dll"}

RE_ROUTE = re.compile(r"@(?:\w+|\w+\.\w+)\.(get|post|put|delete|patch|options)\(\s*(['\"])([^'\"]+)\2")
RE_MODEL = re.compile(r"^class\s+(\w+)\(([^)]*(?:Base|Model|declarative_base|\.Model)[^)]*)\):\s*$")
RE_COLUMN = re.compile(r"^\s+(\w+)\s*=\s*Column\(")
RE_ENV = re.compile(r"os\.environ\.(?:get|getenv)\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", re.MULTILINE)
RE_ENV2 = re.compile(r"os\.getenv\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", re.MULTILINE)
RE_FASTAPI = re.compile(r"FastAPI\s*\(")
RE_FLASK = re.compile(r"Flask\s*\(")
RE_UVICORN = re.compile(r"uvicorn\s+([\w\.:]+)\s*(?:--host\s+([\w\.]+))?\s*(?:--port\s+(\d+))?")
RE_VERSION_PY = re.compile(r"(?:__version__|VERSION)\s*=\s*['\"]([^'\"]+)['\"]")


@dataclass
class Endpoint:
    method: str
    path: str
    file: str


@dataclass
class ModelInfo:
    name: str
    table: Optional[str]
    fields: List[str]
    file: str


@dataclass
class ProjectContext:
    root: str
    name: str
    framework: Optional[str] = None
    entry_point: Optional[str] = None
    how_to_run: Optional[str] = None
    version: Optional[str] = None
    endpoints: List[Endpoint] = field(default_factory=list)
    models: List[ModelInfo] = field(default_factory=list)
    env_vars: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    html_pages: List[str] = field(default_factory=list)


def _iter_text_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in SKIP_EXTS:
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            yield rel.replace(os.sep, "/")


def _is_code(path: str) -> bool:
    return path.endswith((".py", ".js", ".ts", ".yml", ".yaml", ".toml", ".html"))


def _read(root: Path, rel: str) -> str:
    try:
        p = root / rel
        if p.stat().st_size > 512 * 1024:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def scan(root, allow_tests=True) -> ProjectContext:
    root = Path(root)
    name = root.name or os.path.basename(os.path.abspath(root))
    ctx = ProjectContext(root=str(root), name=name)
    files = sorted(_iter_text_files(root))

    for rel in files:
        if rel.startswith(("tests/", "test_", "tests_")) or rel.endswith(("_test.py", "test.py")):
            ctx.tests.append(rel)
            continue
        if rel.endswith(".html"):
            ctx.html_pages.append(rel)

        # version marker file (VERSION is not code, so handle before _is_code)
        if ctx.version is None and (rel == "VERSION" or rel.endswith("/VERSION")):
            ctx.version = _read(root, rel).strip()

        if not _is_code(rel):
            continue
        content = _read(root, rel)
        if not content:
            continue

        # framework + entry point
        if RE_FASTAPI.search(content):
            ctx.framework = "fastapi"
            if ctx.entry_point is None:
                ctx.entry_point = rel
        if RE_FLASK.search(content):
            ctx.framework = "flask"
            if ctx.entry_point is None:
                ctx.entry_point = rel

        # routes
        for m in RE_ROUTE.finditer(content):
            ctx.endpoints.append(Endpoint(m.group(1).upper(), m.group(3), rel))

        # models
        lines = content.splitlines()
        current_model = None
        for line in lines:
            mod = RE_MODEL.match(line)
            if mod and current_model is None:
                current_model = ModelInfo(name=mod.group(1), table=None, fields=[], file=rel)
                ctx.models.append(current_model)
                continue
            if current_model is not None:
                col = RE_COLUMN.match(line)
                tm = re.match(r"\s+__tablename__\s*=\s*['\"]([^'\"]+)['\"]", line)
                if tm:
                    current_model.table = tm.group(1)
                elif col:
                    current_model.fields.append(col.group(1))
                elif line.strip() and not line.startswith((" ", "\t")):
                    current_model = None

        # env vars
        ctx.env_vars.extend(RE_ENV.findall(content))
        ctx.env_vars.extend(RE_ENV2.findall(content))

    ctx.env_vars = sorted(set(ctx.env_vars))
    ctx.source_files = [f for f in files if f.endswith(".py")]

    if ctx.framework is None and ctx.html_pages:
        ctx.framework = "static"
    _detect_run_commands(root, ctx)
    return ctx


def _detect_run_commands(root: Path, ctx: ProjectContext):
    for fname in ("README.md", "run.bat", "run.sh", "Makefile", "makefile"):
        p = root / fname
        if not p.is_file():
            continue
        content = p.read_text(encoding="utf-8", errors="replace")
        m = RE_UVICORN.search(content)
        if m:
            target = m.group(1)
            port = m.group(3) or "8000"
            ctx.how_to_run = f"uvicorn {target} (port {port})"
            if ctx.framework is None:
                ctx.framework = "fastapi"
            return
    if ctx.framework == "static":
        ctx.how_to_run = "serve the folder statically (e.g. python -m http.server)"
    elif ctx.framework == "fastapi" and ctx.entry_point:
        ctx.how_to_run = f"uvicorn {ctx.entry_point[:-3].replace('/', '.')}:app --reload"


def render_structure(ctx: ProjectContext) -> str:
    lines = [
        f"# {ctx.name}",
        f"framework: {ctx.framework or 'unknown'}",
        f"entry point: {ctx.entry_point or '-'}",
        f"run: {ctx.how_to_run or '-'}",
        f"version: {ctx.version or '-'}",
    ]
    if ctx.models:
        lines.append("\n## models")
        for m in ctx.models:
            fields = ", ".join(m.fields[:12]) + ("..." if len(m.fields) > 12 else "")
            lines.append(f"- {m.name} ({m.table or '?'}) [{fields}]  <- {m.file}")
    if ctx.endpoints:
        lines.append("\n## endpoints")
        for e in ctx.endpoints[:60]:
            lines.append(f"- {e.method:6s} {e.path:<48} {e.file}")
        if len(ctx.endpoints) > 60:
            lines.append(f"... +{len(ctx.endpoints) - 60} more")
    if ctx.env_vars:
        lines.append("\n## env vars")
        lines.append(", ".join(ctx.env_vars))
    if ctx.tests:
        lines.append("\n## tests")
        lines.append(", ".join(ctx.tests[:20]))
    if ctx.html_pages:
        lines.append("\n## static pages")
        lines.append(", ".join(ctx.html_pages))
    return "\n".join(lines)


def render_ai(ctx: ProjectContext) -> str:
    """Compact context pack optimized for an AI agent's initial context window."""
    run = ctx.how_to_run or (f"uvicorn {ctx.entry_point[:-3].replace('/', '.')}:app --reload" if ctx.entry_point else "unknown")
    lines = [
        f"PROJECT: {ctx.name}",
        f"FRAMEWORK: {ctx.framework or 'unknown'}",
        f"ENTRY: {ctx.entry_point or '-'}",
        f"RUN: {run}",
        f"VERSION: {ctx.version or '-'}",
        f"TEST_CMD: python -m pytest",
        f"TESTS: {', '.join(ctx.tests[:10]) or 'none'}",
    ]
    if ctx.models:
        lines.append("MODELS:")
        for m in ctx.models:
            lines.append(f"  {m.name} table={m.table or '?'} cols=[{', '.join(m.fields)}] file={m.file}")
    if ctx.endpoints:
        lines.append("ENDPOINTS:")
        for e in ctx.endpoints:
            lines.append(f"  {e.method} {e.path}  ({e.file})")
    if ctx.env_vars:
        lines.append(f"ENV_VARS: {', '.join(ctx.env_vars)}")
    if ctx.html_pages:
        lines.append(f"STATIC_PAGES: {', '.join(ctx.html_pages)}")
    return "\n".join(lines)


__all__ = ["scan", "render_structure", "render_ai", "ProjectContext"]