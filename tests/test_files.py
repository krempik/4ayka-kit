import pytest

from ayka.files import FileGuard


@pytest.fixture
def guard():
    return FileGuard()


def test_unsafe_extensions(guard):
    assert guard.check_extension("evil.html") is False
    assert guard.check_extension("upload.php") is False
    assert guard.check_extension("app.js") is False
    assert guard.check_extension("note.txt") is True
    assert guard.check_extension("photo.png") is True


def test_extension_case_insensitive(guard):
    assert guard.check_extension("EVIL.HTML") is False


def test_blocked_mimes(guard):
    assert guard.check_mime("text/html") is False
    assert guard.check_mime("image/svg+xml") is False


def test_mime_parameter_stripping(guard):
    assert guard.check_mime("image/png; charset=binary") is True


def test_empty_mime_rejected(guard):
    assert guard.check_mime("") is False
    assert guard.check_mime(None) is False


def test_size_limit():
    g = FileGuard(max_size_bytes=10)
    assert g.check_size(5) is True
    assert g.check_size(11) is False


def test_validate_ok(guard):
    assert guard.validate("photo.png", "image/png", 1024) == ""


def test_validate_errors(guard):
    assert guard.validate("page.html", "text/html", 3) != ""
    assert guard.validate("script.py", "text/x-python", 3) != ""
    assert guard.validate("big.bin", "application/octet-stream", 2**40) != ""