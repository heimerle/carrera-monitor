"""SQLAlchemy engine, session factory, and pragma wiring for the race-management DB.

A separate connection pool / database from the JSONL event log. The
engine is created lazily so importing this module never touches disk;
:func:`get_engine` is the entry point used by services + tests.

Pragmas (`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`) are
applied on every new connection via an ``@event.listens_for(engine,
"connect")`` hook, per
[contracts/database-schema.md](../specs/001-race-management/contracts/database-schema.md).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all race-management ORM models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _attach_pragmas(engine: Engine) -> None:
    """Issue SQLite pragmas on every new connection."""

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn: Any, _record: Any) -> None:  # pragma: no cover - trivial
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()


def _ensure_parent_dir(url: str) -> None:
    """For ``sqlite:///<path>`` URLs, create the parent dir if it doesn't exist."""
    if not url.startswith("sqlite:"):
        return
    parsed = urlparse(url)
    # SQLAlchemy uses sqlite:///<relative> or sqlite:////<absolute> ; the
    # path lives in parsed.path. Skip ``:memory:`` and empty paths.
    path = parsed.path.lstrip("/")
    if not path or path == ":memory:":
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def configure_engine(url: str, *, echo: bool = False) -> Engine:
    """Create (or replace) the global engine + session factory for ``url``."""
    global _engine, _SessionLocal
    _ensure_parent_dir(url)
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 5.0}
    _engine = create_engine(url, echo=echo, connect_args=connect_args, future=True)
    _attach_pragmas(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    logger.debug("database: engine configured for %s (echo=%s)", url, echo)
    return _engine


def get_engine() -> Engine:
    """Return the current engine; configures a default if not yet done."""
    if _engine is None:
        configure_engine("sqlite:///./data/carrera_dashboard.sqlite3")
    assert _engine is not None
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def SessionLocal() -> Session:
    """Open a new ORM session bound to the current engine."""
    return get_sessionmaker()()


def init_db(url: str | None = None, *, echo: bool = False) -> Engine:
    """Configure the engine (if ``url`` given) and create all tables.

    Idempotent: ``Base.metadata.create_all`` is a no-op when tables already
    exist. Safe to call from ``src/main.py`` on every startup.
    """
    # Import models so they are registered on Base.metadata before create_all.
    from . import models  # noqa: F401  (side-effect import)

    if url is not None:
        configure_engine(url, echo=echo)
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("database: schema initialized")
    return engine


__all__ = [
    "Base",
    "SessionLocal",
    "configure_engine",
    "get_engine",
    "get_sessionmaker",
    "init_db",
]
