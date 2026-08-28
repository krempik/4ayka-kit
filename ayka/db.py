"""Database building blocks: engine factory, declarative Base, zero-loss migration.

`ensure_schema(Base, engine)` runs `create_all` and then adds any missing columns
with `ALTER TABLE ADD COLUMN` — the same auto-migration used in H4ck Messenger,
so schema changes never wipe existing data.

Generated applications keep their *own* Base/engine (importing this module only
for helpers), so several apps can share one installed copy of ayka-kit.
"""
import logging
from typing import List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

log = logging.getLogger("ayka.db")

Base = declarative_base()


def make_engine(db_path: str, *, check_same_thread: bool = False):
    """SQLite engine. check_same_thread defaults to False because FastAPI's sync
    endpoints (and TestClient) dispatch into a thread pool."""
    db_path = db_path or ":memory:"
    if db_path == ":memory:":
        return create_engine("sqlite://", connect_args={"check_same_thread": check_same_thread})
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": check_same_thread},
        pool_pre_ping=True,
    )


def make_session(engine):
    return sessionmaker(bind=engine)


def auto_migrate(Base_cls, engine) -> List[str]:
    """Add missing columns to existing tables. Returns list of added "table.column"."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    migrated = []

    for table_name, table in Base_cls.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            col_type = col.type.compile(engine.dialect)
            nullable = "NULL" if col.nullable else "NOT NULL"
            default_val = ""
            if col.default is not None and col.default.is_scalar:
                default_val = f" DEFAULT {repr(col.default.arg)}"
            elif col.nullable:
                default_val = " DEFAULT NULL"
            sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {nullable}{default_val}"
            try:
                with engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
                migrated.append(f"{table_name}.{col.name}")
            except Exception as e:  # noqa: BLE001 - migration must never crash the app
                log.warning(f"Migration skip {table_name}.{col.name}: {e}")

    if migrated:
        log.info("Auto-migrated columns: %s", ", ".join(migrated))
    return migrated


def ensure_schema(Base_cls, engine) -> List[str]:
    """create_all + auto_migrate. Idempotent, safe to call on every boot."""
    Base_cls.metadata.create_all(bind=engine)
    return auto_migrate(Base_cls, engine)