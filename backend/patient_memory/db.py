"""Engine / session factory for the patient memory database."""

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend import config
from backend.patient_memory.models import Base

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine(url: Optional[str] = None) -> Engine:
    global _engine, _SessionLocal
    if _engine is None or url is not None:
        url = url or config.DATABASE_URL
        kwargs = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(engine, "connect")
            def _pragmas(dbapi_conn, _):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()
        Base.metadata.create_all(engine)
        _engine = engine
        _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    get_engine()
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
