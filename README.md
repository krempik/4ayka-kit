# 4ayka-kit

AI-friendly framework toolkit. Build FastAPI services from a short YAML spec,
scan any project into a compact context for AI agents, and reuse solid building
blocks (JWT auth, rate limiting, MIME guards, DB auto-migration).

```bash
pip install -e .
```

## CLI

| Command | What it does |
|---|---|
| `ayka new fastapi myapp` | scaffold `spec.yaml` + `run.bat` + `.gitignore` (then `ayka gen`) |
| `ayka new game mygame` | scaffold a canvas game (`index.html` + `style.css` + `main.js`) |
| `ayka gen` | generate/regenerate `app/` + CI + tests from `spec.yaml` |
| `ayka ctx [DIR]` | scan project -> human-friendly structure report |
| `ayka ctx [DIR] --ai` | scan project -> compact context pack for AI agents |
| `ayka ctx --out FILE` | write the report to a file |
| `ayka version show` | print ayka-kit's own version |
| `ayka version bump patch|minor|major` | bump ayka-kit's version in place |

(`ayka.version` also exposes `read_version`/`bump_file` helpers for *project*
VERSION files.)

## spec.yaml -> FastAPI app

16 lines in, a working CRUD service out:

```yaml
project: { name: notes, title: Notes, auth: jwt }
resources:
  notes:
    fields: { title: str, body: text, tags: 'list[str]' }
    search: [title]
    crud: full
  reminders:
    fields: { note_id: int, at: datetime }
    crud: create
```

Run `ayka gen` -> `app/` with models, schemas, routers, JWT auth (`/api/auth/*`),
rate limiting, `/api/version`, auto-migration. Then:

```bash
uvicorn app.main:app --reload
```

### crud modes (per resource)

- `read` — `GET /api/name` + `GET /api/name/{id}`
- `create` — `POST /api/name` only (append-only log)
- `write` — list + `POST` + `PUT` + `DELETE`
- `full` — `write` + `GET /id`
- `none` — no endpoints

With `auth: jwt`, non-`public` resources gain `owner_id` and are automatically
scoped to the current user. Field types: `str, text, int, float, bool, date,
datetime, json, list[str], password`.

`ayka ctx` (that same "context scanner") then understands the generated project,
so you — or an AI agent — can keep going instantly.

## Building blocks

- `ayka.auth` — pbkdf2 hashing, HS256 access/refresh JWT, `get_current_user`, `build_auth_router()`
- `ayka.db` — `ensure_schema()` (create_all + zero-loss `ALTER TABLE` auto-migration)
- `ayka.middleware` — IP rate limiter (multiproxy-aware), reusable FastAPI middleware
- `ayka.files` — `FileGuard`: MIME allow/deny lists, unsafe extension blacklist
- `ayka.version` — VERSION file read/write + bump (patch/minor/major)
- `ayka.scanner` — project AST-ish surface scanner

## Roadmap

- phase 2: WebSocket lobby generator (`spec.rooms`), webpush subscriptions
- phase 3: `ayka-maven` — same codegen idea for Java (optional, after a real Java project)