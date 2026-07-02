import importlib
import sqlite3
from pathlib import Path


def test_init_db_repairs_legacy_sqlite_task_columns(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.db"
    sqlite3.connect(database_path).executescript(
        """
        CREATE TABLE task (
            id CHAR(32) PRIMARY KEY NOT NULL,
            input_type VARCHAR NOT NULL,
            content VARCHAR NOT NULL,
            status VARCHAR(14) NOT NULL,
            current_stage VARCHAR NOT NULL,
            error_message VARCHAR,
            understanding JSON,
            retrieval_hits JSON NOT NULL,
            workflow_result JSON,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE knowledgechunk (
            id CHAR(32) PRIMARY KEY NOT NULL,
            document_id CHAR(32) NOT NULL,
            chunk_index INTEGER NOT NULL,
            content VARCHAR NOT NULL,
            created_at DATETIME NOT NULL
        );
        """
    ).close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    from app.core.settings import get_settings
    import app.core.db as db_module

    get_settings.cache_clear()
    reloaded_db_module = importlib.reload(db_module)

    try:
        reloaded_db_module.init_db()

        connection = sqlite3.connect(database_path)
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(task)").fetchall()
        }
        knowledge_chunk_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(knowledgechunk)").fetchall()
        }
        indexes = {
            row[1]
            for row in connection.execute("PRAGMA index_list(task)").fetchall()
        }
        connection.close()

        assert {"knowledge_domain", "review", "approved_snapshot"}.issubset(columns)
        assert {"retrieval_text", "embedding_vector"}.issubset(knowledge_chunk_columns)
        assert "ix_task_knowledge_domain" in indexes
    finally:
        get_settings.cache_clear()
        importlib.reload(db_module)
