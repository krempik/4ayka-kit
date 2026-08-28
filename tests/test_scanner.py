from ayka.scanner import render_ai, render_structure, scan


def test_scan_detects_fastapi_surface(tmp_path):
    (tmp_path / "server").mkdir()
    (tmp_path / "tests").mkdir()

    (tmp_path / "server" / "main.py").write_text(
        "import os\n"
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "\n"
        "@app.get('/api/health')\n"
        "def health():\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    (tmp_path / "server" / "routes.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.post('/api/msg')\n"
        "def send():\n"
        "    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "server" / "models.py").write_text(
        "import os\n"
        "from sqlalchemy.ext.declarative import declarative_base\n"
        "Base = declarative_base()\n"
        "class Message(Base):\n"
        '    __tablename__ = "message"\n'
        "    id = Column(Integer, primary_key=True)\n"
        "    body = Column(String)\n"
        "SECRET = os.environ.get('MSG_SECRET')\n"
        "PORT = os.getenv('PORT')\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# demo\nuvicorn server.main:app --port 8181\n", encoding="utf-8"
    )
    (tmp_path / "tests" / "test_x.py").write_text("def test(): pass\n", encoding="utf-8")
    (tmp_path / "VERSION").write_text("0.2.0\n", encoding="utf-8")

    ctx = scan(tmp_path)
    assert ctx.framework == "fastapi"
    assert ctx.entry_point == "server/main.py"
    assert ctx.version == "0.2.0"
    assert ctx.how_to_run and "8181" in ctx.how_to_run

    methods = {(e.method, e.path) for e in ctx.endpoints}
    assert ("GET", "/api/health") in methods
    assert ("POST", "/api/msg") in methods

    assert any(m.name == "Message" and m.table == "message" for m in ctx.models)
    msg = next(m for m in ctx.models if m.name == "Message")
    assert "body" in msg.fields

    assert "MSG_SECRET" in ctx.env_vars
    assert "PORT" in ctx.env_vars
    assert "tests/test_x.py" in ctx.tests


def test_scan_static(tmp_path):
    (tmp_path / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
    ctx = scan(tmp_path)
    assert ctx.framework == "static"
    assert ctx.html_pages == ["index.html"]


def test_scan_skips_junk(tmp_path):
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "x.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    ctx = scan(tmp_path)
    assert ctx.framework is None
    assert ctx.entry_point is None


def test_render_ai_and_structure_contain_surface(tmp_path):
    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/x')\ndef x(): return 1\n",
        encoding="utf-8",
    )
    ctx = scan(tmp_path)
    ai = render_ai(ctx)
    struct = render_structure(ctx)
    assert "GET /x" in ai
    assert "GET" in struct and "/x" in struct