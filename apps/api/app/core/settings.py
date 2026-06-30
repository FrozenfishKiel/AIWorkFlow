from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _get_first_env(*names: str, default: str | None = None) -> str | None:
    """Return the first non-empty environment variable from the provided names."""

    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def derive_default_repo_root(current_file: Path | None = None) -> Path:
    """Infer the repository root from the settings module location.

    The code runs in two stable layouts:
    - Windows checkout: ``.../apps/api/app/core/settings.py``
    - Docker container: ``/app/app/core/settings.py``

    This keeps the runtime directory stable in both places without requiring
    callers to hard-code path layout assumptions.
    """

    resolved = current_file or Path(__file__)

    for parent in resolved.parents:
        if parent.name == "api" and parent.parent.name == "apps":
            return parent.parent.parent

    for parent in resolved.parents:
        if parent.name == "app" and parent.parent != parent:
            return parent.parent

    return resolved.parent


class Settings:
    """Centralized runtime settings for the API and worker process."""

    def __init__(self) -> None:
        repo_root = derive_default_repo_root()
        runtime_root = Path(
            _get_first_env(
                "APP_RUNTIME_DIR",
                "AI_CONTENT_OPS_RUNTIME_DIR",
                default=str(repo_root / ".runtime"),
            )
        )
        data_root = runtime_root / "data"
        logs_root = runtime_root / "logs"
        uploads_root = runtime_root / "uploads"
        exports_root = runtime_root / "exports"

        self.repo_root = repo_root
        self.runtime_root = runtime_root
        self.data_root = data_root
        self.logs_root = logs_root
        self.uploads_root = uploads_root
        self.exports_root = exports_root

        default_db_path = data_root / "app.db"
        self.database_url = _get_first_env(
            "DATABASE_URL",
            "AI_CONTENT_OPS_DATABASE_URL",
            default=f"sqlite:///{default_db_path.as_posix()}",
        )
        self.celery_broker_url = _get_first_env(
            "CELERY_BROKER_URL",
            "AI_CONTENT_OPS_CELERY_BROKER_URL",
            default="redis://127.0.0.1:6379/0",
        )
        self.celery_result_backend = _get_first_env(
            "CELERY_RESULT_BACKEND",
            "AI_CONTENT_OPS_CELERY_RESULT_BACKEND",
            default=self.celery_broker_url,
        )
        self.api_access_token = _get_first_env(
            "API_ACCESS_TOKEN",
            "AI_CONTENT_OPS_API_ACCESS_TOKEN",
            default=None,
        )
        self.allowed_upload_extensions = {
            ".txt",
            ".md",
            ".pdf",
            ".docx",
            ".html",
        }
        self.max_upload_bytes = 10 * 1024 * 1024
        self.cors_origins = [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]

    def ensure_runtime_directories(self) -> None:
        """Create runtime folders in one place so generated files stay contained."""

        for path in (
            self.runtime_root,
            self.data_root,
            self.logs_root,
            self.uploads_root,
            self.exports_root,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton after creating runtime dirs."""

    settings = Settings()
    settings.ensure_runtime_directories()
    return settings
