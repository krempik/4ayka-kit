import sys
import textwrap
from pathlib import Path

from fastapi.testclient import TestClient

from ayka.generator.gen import generate
from ayka.generator.spec import load_spec

SPEC = """\
project:
  name: notes
  title: Notes
  auth: jwt
  db: data/notes.db

resources:
  notes:
    fields: {title: str, body: text, tags: 'list[str]'}
    search: [title, body]
    crud: full

  public_links:
    fields: {url: str, label: str}
    crud: read
    public: true

  events:
    fields: {kind: str, at: datetime, count: int}
    crud: create
"""


def _build(tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(textwrap.dedent(SPEC), encoding="utf-8")
    spec = load_spec(spec_path)
    written = generate(spec, tmp_path)
    for key in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[key]
    sys.path.insert(0, str(tmp_path))
    try:
        import app.main as main_mod  # noqa: PLC0415

        return spec, main_mod
    finally:
        try:
            sys.path.remove(str(tmp_path))
        except ValueError:
            pass


def test_generate_writes_all_files(tmp_path):
    (tmp_path / "spec.yaml").write_text(textwrap.dedent(SPEC), encoding="utf-8")
    spec = load_spec(tmp_path / "spec.yaml")
    written = generate(spec, tmp_path)
    for rel in (
        "app/main.py",
        "app/config.py",
        "app/database.py",
        "app/models.py",
        "app/schemas.py",
        "app/routes.py",
        "run.py",
        "requirements.txt",
        "README.md",
        ".gitignore",
        "tests/test_api.py",
        ".github/workflows/ci.yml",
    ):
        assert rel in written
        assert (tmp_path / rel).is_file()


def test_full_generated_app_lifecycle(tmp_path):
    spec, main_mod = _build(tmp_path)
    client = TestClient(main_mod.app)

    # health + version
    assert client.get("/api/health").status_code == 200
    v = client.get("/api/version").json()
    assert v["name"] == "notes"
    assert v["version"]

    # register two users
    r1 = client.post("/api/auth/register",
                     json={"username": "alice", "password": "supersecret", "display_name": "Alice"})
    assert r1.status_code == 201, r1.text
    t1 = r1.json()["access_token"]
    h1 = {"Authorization": "Bearer " + t1}
    alice_id = client.get("/api/auth/me", headers=h1).json()["id"]

    r2 = client.post("/api/auth/register", json={"username": "bob", "password": "supersecret2"})
    assert r2.status_code == 201, r2.text
    h2 = {"Authorization": "Bearer " + r2.json()["access_token"]}

    # duplicate username -> 409
    dup = client.post("/api/auth/register", json={"username": "alice", "password": "whatever123"})
    assert dup.status_code == 409

    # unauthenticated create -> 401
    assert client.post("/api/notes", json={"title": "x", "body": "y"}).status_code == 401

    # create note as alice
    r = client.post("/api/notes", headers=h1, json={"title": "hello", "body": "world", "tags": ["a", "b"]})
    assert r.status_code == 201, r.text
    note = r.json()
    nid = note["id"]
    assert note["owner_id"] == alice_id
    assert note["tags"] == ["a", "b"]

    # owner can list and search
    assert len(client.get("/api/notes", headers=h1).json()) == 1
    found = client.get("/api/notes?q=world", headers=h1).json()
    assert len(found) == 1 and found[0]["id"] == nid

    # owner isolation
    assert client.get("/api/notes", headers=h2).json() == []
    assert client.get(f"/api/notes/{nid}", headers=h2).status_code == 404
    assert client.put(f"/api/notes/{nid}", headers=h2, json={"title": "hacked"}).status_code == 404
    assert client.delete(f"/api/notes/{nid}", headers=h2).status_code == 404

    # update + partial update
    u = client.put(f"/api/notes/{nid}", headers=h1, json={"body": "updated"})
    assert u.status_code == 200
    assert u.json()["body"] == "updated"
    assert u.json()["title"] == "hello"  # untouched field survives

    # delete
    assert client.delete(f"/api/notes/{nid}", headers=h1).status_code == 204
    assert client.get("/api/notes", headers=h1).json() == []

    # public read-only resource: readable anonymously, no POST route
    assert client.get("/api/public_links").json() == []
    assert client.post("/api/public_links", json={"url": "https://x.test", "label": "x"}).status_code == 405

    # append-only resource: POST works with owner, no list/get
    ev = client.post("/api/events", headers=h1,
                     json={"kind": "ping", "at": "2026-01-01T00:00:00", "count": 3})
    assert ev.status_code == 201, ev.text
    assert ev.json()["owner_id"] == alice_id
    assert ev.json()["count"] == 3
    assert client.get("/api/events", headers=h1).status_code == 405

    # login + refresh flow
    login = client.post("/api/auth/login", json={"username": "bob", "password": "supersecret2"})
    assert login.status_code == 200
    ref = client.post("/api/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert ref.status_code == 200
    assert "access_token" in ref.json()

    # bad login
    assert client.post("/api/auth/login", json={"username": "bob", "password": "wrong"}).status_code == 401


def test_generated_app_without_auth(tmp_path):
    (tmp_path / "spec.yaml").write_text(
        textwrap.dedent(
            """\
            project: {name: paste, title: Paste, auth: false}
            resources:
              pastes:
                fields: {content: text}
                crud: full
            """
        ),
        encoding="utf-8",
    )
    spec = load_spec(tmp_path / "spec.yaml")
    generate(spec, tmp_path)
    for key in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[key]
    sys.path.insert(0, str(tmp_path))
    try:
        import app.main as main_mod  # noqa: PLC0415

        client = TestClient(main_mod.app)
        r = client.post("/api/pastes", json={"content": "hello world"})
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["content"] == "hello world"
        assert "owner_id" not in item
        lst = client.get("/api/pastes").json()
        assert len(lst) == 1
        assert client.delete(f"/api/pastes/{item['id']}").status_code == 204
    finally:
        try:
            sys.path.remove(str(tmp_path))
        except ValueError:
            pass


def test_generated_ci_and_readme_exist(tmp_path):
    (tmp_path / "spec.yaml").write_text(textwrap.dedent(SPEC), encoding="utf-8")
    spec = load_spec(tmp_path / "spec.yaml")
    generate(spec, tmp_path)
    ci = (tmp_path / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "test:" in ci and "pytest" in ci
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "/api/auth/register" in readme
    assert "/api/notes" in readme


def test_generated_tests_respect_crud_modes(tmp_path):
    (tmp_path / "spec.yaml").write_text(textwrap.dedent(SPEC), encoding="utf-8")
    spec = load_spec(tmp_path / "spec.yaml")
    generate(spec, tmp_path)
    test_text = (tmp_path / "tests" / "test_api.py").read_text(encoding="utf-8")

    # full resource -> create + list
    assert "client.post('/api/notes'" in test_text
    assert "client.get('/api/notes'" in test_text

    # read-only resource -> list only, no POST
    assert "client.get('/api/public_links'" in test_text
    assert "client.post('/api/public_links'" not in test_text

    # append-only resource -> POST only, no GET
    assert "client.post('/api/events'" in test_text
    assert "client.get('/api/events'" not in test_text

    # clean DB per run
    assert "os.remove(os.environ['NOTES_DB'])" in test_text