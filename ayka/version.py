"""Version helpers: pure bump(), package current_version/bump_version, and
generic read/write/bump for PROJECT VERSION files.

Scheme (matches bump_version.py — patch/minor/major):
  patch: 2.2.1 -> 2.2.2  (bug fixes)
  minor: 2.2.1 -> 2.3.0  (features)
  major: 2.2.1 -> 3.0.0  (breaking)
"""
import re
from pathlib import Path
from typing import Optional

_PKG_FILE = Path(__file__).resolve().parent / "__init__.py"
_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')


def bump(version: str, bump_type: str) -> str:
    parts = list(map(int, version.split(".")))
    while len(parts) < 3:
        parts.append(0)

    if bump_type == "patch":
        parts[2] += 1
    elif bump_type == "minor":
        parts[1] += 1
        parts[2] = 0
    elif bump_type == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")

    return ".".join(map(str, parts))


def current_version() -> str:
    """Return ayka-kit's own __version__ (from ayka/__init__.py)."""
    text = _PKG_FILE.read_text(encoding="utf-8")
    m = _VERSION_RE.search(text)
    if not m:
        return "0.0.0"
    return m.group(1)


def bump_version(bump_type: str) -> str:
    """Bump ayka-kit's own __version__ in place; returns the new version."""
    new = bump(current_version(), bump_type)
    text = _PKG_FILE.read_text(encoding="utf-8")
    text = _VERSION_RE.sub(f'__version__ = "{new}"', text, count=1)
    _PKG_FILE.write_text(text, encoding="utf-8")
    return new


def read_version(version_file: Path) -> Optional[str]:
    if not Path(version_file).is_file():
        return None
    return Path(version_file).read_text(encoding="utf-8").strip()


def write_version(version_file: Path, version: str) -> None:
    Path(version_file).write_text(version.strip() + "\n", encoding="utf-8")


def bump_file(version_file: Path, bump_type: str) -> Optional[str]:
    current = read_version(version_file)
    if current is None:
        return None
    new_version = bump(current, bump_type)
    write_version(version_file, new_version)
    return new_version