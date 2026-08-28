import textwrap

import pytest
import yaml

from ayka.generator.spec import load_project, load_spec, DEFAULT_SPEC


def test_parse_default():
    spec = load_project(yaml.safe_load(DEFAULT_SPEC))
    assert spec.name == "notes"
    assert spec.auth
    assert set(spec.resources) == {"notes", "reminders"}

    notes = spec.resources["notes"]
    assert [f.name for f in notes.fields] == ["title", "body", "tags"]
    assert notes.crud == "full"
    assert notes.search == ["title", "body"]
    assert not notes.public

    rem = spec.resources["reminders"]
    assert rem.crud == "create"


def test_parse_custom():
    spec = load_project(
        {
            "project": {"name": "blog", "title": "Blog", "auth": False},
            "resources": {
                "posts": {
                    "fields": ["title", {"published": "bool"}],
                    "crud": "read",
                    "search": "title",
                    "public": True,
                }
            },
        }
    )
    assert spec.name == "blog"
    assert not spec.auth
    posts = spec.resources["posts"]
    assert posts.crud == "read"
    assert posts.public
    assert posts.search == ["title"]
    assert {f.name for f in posts.fields} == {"title", "published"}


def test_auth_string_jwt():
    spec = load_project({"project": {"name": "x", "auth": "jwt"}, "resources": {}})
    assert spec.auth


def test_bad_field_type():
    with pytest.raises(ValueError):
        load_project({"project": {"name": "x"}, "resources": {"p": {"fields": {"a": "wat"}}}})


def test_crud_fallback_unknown():
    spec = load_project(
        {"project": {"name": "x"}, "resources": {"p": {"fields": {"a": "str"}, "crud": "nonsense"}}}
    )
    assert spec.resources["p"].crud == "full"


def test_load_spec_file(tmp_path):
    f = tmp_path / "spec.yaml"
    f.write_text(
        textwrap.dedent(
            """\
            project:
              name: foo
              auth: false
              db: data/foo.db
            resources:
              bars:
                fields: {name: str, count: int}
                crud: full
            """
        ),
        encoding="utf-8",
    )
    spec = load_spec(f)
    assert spec.name == "foo"
    assert spec.db_file == "data/foo.db"
    assert "bars" in spec.resources