"""spec.yaml parsing and validation.

Minimal declarative schema for FastAPI services:

    project: { name: notes, title: Notes, auth: jwt }
    resources:
      notes:
        fields: { title: str, body: text, tags: list[str] }
        search: [title]
        crud: full          # full | read | write | create | none
        public: false       # true => no owner scoping
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

DEFAULT_CRUD = "full"

FIELD_TYPES = {
    "str": "string",
    "text": "text",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "date": "date",
    "datetime": "datetime",
    "json": "json",
    "list[str]": "list",
    "password": "password",
}

CRUD_MODES = {"full", "read", "write", "create", "none"}

DEFAULT_SPEC = """# 4ayka-kit project spec
# resources are auto-generated into app/ via: ayka gen
project:
  name: notes
  title: Notes
  auth: jwt

resources:
  notes:
    fields:
      title: str
      body: text
      tags: list[str]
    search: [title, body]
    crud: full

  reminders:
    fields:
      note_id: int
      at: datetime
    crud: create
"""


@dataclass
class FieldSpec:
    name: str
    type: str

    @property
    def kind(self) -> str:
        return FIELD_TYPES.get(self.type, "string")


@dataclass
class ResourceSpec:
    name: str
    fields: List[FieldSpec] = field(default_factory=list)
    crud: str = DEFAULT_CRUD
    search: List[str] = field(default_factory=list)
    public: bool = False

    @property
    def table(self) -> str:
        return self.name.replace("-", "_")


@dataclass
class ProjectSpec:
    name: str = "app"
    title: str = "App"
    auth: bool = False
    db_file: str = "data/app.db"
    resources: Dict[str, ResourceSpec] = field(default_factory=dict)

    @property
    def package(self) -> str:
        return self.name.replace("-", "_")


def _field_list(field_def) -> List[FieldSpec]:
    result = []
    if isinstance(field_def, dict):
        items = field_def.items()
    elif isinstance(field_def, list):
        result = []
        for f in field_def:
            if isinstance(f, dict):
                result.append(FieldSpec(**{"name": str(next(iter(f))), "type": str(f[next(iter(f))])}))
            elif isinstance(f, str) and ":" in f:
                name, typ = f.split(":", 1)
                result.append(FieldSpec(name=name.strip(), type=typ.strip()))
            elif isinstance(f, str):
                result.append(FieldSpec(name=f.strip(), type="str"))
            else:
                raise ValueError(f"Bad field entry: {f!r}")
        for spec in result:
            if spec.type not in FIELD_TYPES:
                raise ValueError(f"Unsupported field type '{spec.type}' for '{spec.name}'. "
                                 f"Use one of: {', '.join(sorted(FIELD_TYPES))}")
        return result
    else:
        raise ValueError(f"Bad fields definition: {field_def!r}")

    for name, typ in items:
        if isinstance(typ, (list, dict)):
            typ = "list[str]"
        name = str(name).strip()
        typ = str(typ).strip()
        if typ not in FIELD_TYPES:
            raise ValueError(f"Unsupported field type '{typ}' for '{name}'. "
                             f"Use one of: {', '.join(sorted(FIELD_TYPES))}")
        result.append(FieldSpec(name=name, type=typ))
    return result


def load_project(data: dict) -> ProjectSpec:
    project = data.get("project") or {}
    if isinstance(project, str):
        project = {"name": project}
    spec = ProjectSpec(
        name=str(project.get("name", "app")).strip().lower(),
        title=str(project.get("title") or project.get("name") or "App"),
        auth=bool(project.get("auth", project.get("auth", False))),
        db_file=str(project.get("db", "data/" + str(project.get("name", "app")).strip().lower() + ".db")),
    )
    if project.get("auth") in (True, "jwt", "true"):
        spec.auth = True

    for name, cfg in (data.get("resources") or {}).items():
        if isinstance(cfg, list):
            cfg = {"fields": cfg}
        cfg = cfg or {}
        res = ResourceSpec(name=str(name).strip().lower())
        res.fields = _field_list(cfg.get("fields", []))
        crud = str(cfg.get("crud", DEFAULT_CRUD)).lower()
        res.crud = crud if crud in CRUD_MODES else DEFAULT_CRUD
        search = cfg.get("search", [])
        res.search = [search] if isinstance(search, str) else [s for s in (search or [])]
        res.public = bool(cfg.get("public", False))
        spec.resources[res.name] = res
    return spec


def load_spec(path) -> ProjectSpec:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return load_project(data)


__all__ = ["ProjectSpec", "ResourceSpec", "FieldSpec", "load_project", "load_spec", "DEFAULT_SPEC"]