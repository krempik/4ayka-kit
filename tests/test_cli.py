"""CLI entry points: command dispatch and default target resolution.

Regression guard: `Path('') or default` was dead code (Path('') is truthy),
so `ayka gen`/`ayka new` silently wrote into the current directory instead of
the documented default (spec dir / ./<name>).
"""
import textwrap
from pathlib import Path
from types import SimpleNamespace

from ayka.cli import cmd_gen, cmd_new


def _spec_text(name: str) -> str:
    return textwrap.dedent(
        f"""\
        project:
          name: {name}
          title: {name.title()}
        resources:
          items:
            fields:
              title: str
            crud: full
        """
    )


def test_gen_default_target_is_spec_dir(tmp_path, monkeypatch):
    spec_dir = tmp_path / "sub"
    spec_dir.mkdir()
    spec = spec_dir / "spec.yaml"
    spec.write_text(_spec_text("demo"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert cmd_gen(SimpleNamespace(spec=str(spec), target="")) == 0

    assert (spec_dir / "app" / "main.py").is_file()
    assert (spec_dir / "run.py").is_file()
    assert not (tmp_path / "app" / "main.py").exists(), "must not write to cwd"


def test_gen_explicit_target_overrides(tmp_path, monkeypatch):
    spec = tmp_path / "spec.yaml"
    spec.write_text(_spec_text("demo"), encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.chdir(tmp_path)

    assert cmd_gen(SimpleNamespace(spec=str(spec), target=str(out))) == 0

    assert (out / "app" / "main.py").is_file()
    assert not (tmp_path / "app" / "main.py").exists()


def test_gen_missing_spec_returns_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cmd_gen(SimpleNamespace(spec="nope.yaml", target="")) == 1


def test_new_fastapi_default_target_is_name_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert cmd_new(SimpleNamespace(name="mynotes", template="fastapi", target="")) == 0

    proj = tmp_path / "mynotes"
    for rel in ("spec.yaml", "README.md", "run.bat", ".gitignore"):
        assert (proj / rel).is_file()
    assert not (tmp_path / "spec.yaml").exists(), "must not scaffold into cwd"


def test_new_game_default_target_is_name_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert cmd_new(SimpleNamespace(name="pong-clone", template="game", target="")) == 0

    proj = tmp_path / "pong-clone"
    for rel in ("index.html", "style.css", "main.js"):
        assert (proj / rel).is_file()
    assert not (tmp_path / "index.html").exists()


def test_new_explicit_target(tmp_path, monkeypatch):
    out = tmp_path / "elsewhere"
    monkeypatch.chdir(tmp_path)

    assert cmd_new(SimpleNamespace(name="demo", template="game", target=str(out))) == 0

    assert (out / "index.html").is_file()
    assert not (tmp_path / "index.html").exists()