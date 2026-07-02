from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import inspect, text
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


def _repair_sqlite_schema() -> None:
    """Apply additive SQLite patches for local databases created by older slices."""

    if not settings.database_url.startswith("sqlite"):
        return

    required_columns: dict[str, dict[str, str]] = {
        "task": {
            "knowledge_domain": "VARCHAR",
            "review": "JSON",
            "approved_snapshot": "JSON",
        },
        "knowledgechunk": {
            "retrieval_text": "VARCHAR NOT NULL DEFAULT ''",
            "embedding_vector": "JSON NOT NULL DEFAULT '[]'",
        },
    }
    required_indexes: dict[str, str] = {
        "ix_task_knowledge_domain": "CREATE INDEX IF NOT EXISTS ix_task_knowledge_domain ON task (knowledge_domain)",
    }

    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, columns in required_columns.items():
            if not inspector.has_table(table_name):
                continue

            existing_columns = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }
            for column_name, column_sql in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
                )

        for index_sql in required_indexes.values():
            connection.execute(text(index_sql))


def init_db() -> None:
    """Create tables for the current runtime database."""

    from app.models import AuditLog, ExportJob, KnowledgeChunk, KnowledgeDocument, Task

    _ = Task
    _ = AuditLog
    _ = ExportJob
    _ = KnowledgeDocument
    _ = KnowledgeChunk
    SQLModel.metadata.create_all(engine)
    _repair_sqlite_schema()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""

    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager used by background workers and services."""

    with Session(engine) as session:
        yield session
