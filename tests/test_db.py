from sqlalchemy import Column, Integer, String, inspect, text
from sqlalchemy.orm import declarative_base

from ayka.db import ensure_schema, make_engine


def test_ensure_schema_creates():
    engine = make_engine(":memory:")
    Base = declarative_base()

    class Item(Base):
        __tablename__ = "item"
        id = Column(Integer, primary_key=True)

    ensure_schema(Base, engine)
    tables = set(inspect(engine).get_table_names())
    assert "item" in tables


def test_auto_migrate_adds_column(tmp_path):
    db = str(tmp_path / "t.db")
    engine = make_engine(db)

    Base1 = declarative_base()

    class ItemV1(Base1):
        __tablename__ = "item"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    ensure_schema(Base1, engine)

    Base2 = declarative_base()

    class ItemV2(Base2):
        __tablename__ = "item"
        id = Column(Integer, primary_key=True)
        name = Column(String)
        extra = Column(String, default="x")

    added = ensure_schema(Base2, engine)
    assert "item.extra" in added
    cols = {c["name"] for c in inspect(engine).get_columns("item")}
    assert cols == {"id", "name", "extra"}

    # second run is a no-op
    assert ensure_schema(Base2, engine) == []


def test_memory_engine_reusable():
    engine = make_engine(":memory:")
    with engine.connect() as conn:
        assert conn.execute(text("select 1")).all() == [(1,)]