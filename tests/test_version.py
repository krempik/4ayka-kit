import re

from pathlib import Path

from ayka.version import bump, bump_file, current_version, read_version, write_version


def test_bump_patch():
    assert bump("0.1.0", "patch") == "0.1.1"


def test_bump_minor():
    assert bump("0.1.9", "minor") == "0.2.0"


def test_bump_major():
    assert bump("1.2.3", "major") == "2.0.0"


def test_bump_short():
    assert bump("1.2", "patch") == "1.2.1"


def test_bump_unknown():
    try:
        bump("1.0.0", "wat")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_current_version_shape():
    assert re.match(r"\d+\.\d+\.\d+", current_version())


def test_version_file_roundtrip(tmp_path):
    f = tmp_path / "VERSION"
    write_version(f, "1.2.0")
    assert read_version(f) == "1.2.0"
    assert bump_file(f, "patch") == "1.2.1"
    assert read_version(f) == "1.2.1"


def test_bump_file_missing(tmp_path):
    assert bump_file(tmp_path / "nope" / "VERSION", "patch") is None