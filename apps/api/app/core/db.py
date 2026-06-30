from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from app.core.settings import get_settings

settings = get_settings()

connect_args: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
)


def init_db() -> None:
    """Create tables for the current runtime database."""

    from app.models import ExportJob, KnowledgeChunk, KnowledgeDocument, Task

    _ = Task
    _ = ExportJob
    _ = KnowledgeDocument
    _ = KnowledgeChunk
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""

    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager used by background workers and services."""

    with Session(engine) as session:
        yield session
