from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a minimal ``KEY=VALUE`` env file without overriding real env vars."""

    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned_value = value.strip().strip('"').strip("'")
        values[key.strip()] = cleaned_value
    return values


def _get_first_env(*names: str, default: str | None = None) -> str | None:
    """Return the first non-empty environment variable from the provided names."""

    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _parse_bool(value: str | None, *, default: bool) -> bool:
    """Parse a permissive env boolean while preserving an explicit default."""

    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
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
        local_env_file = repo_root / "apps" / "api" / ".env.local"
        file_env = _read_env_file(local_env_file)

        def get_setting(*names: str, default: str | None = None) -> str | None:
            env_value = _get_first_env(*names)
            if env_value is not None:
                return env_value
            for name in names:
                file_value = file_env.get(name)
                if file_value:
                    return file_value
            return default

        runtime_root = Path(
            get_setting(
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
        self.local_env_file = local_env_file
        self.runtime_root = runtime_root
        self.data_root = data_root
        self.logs_root = logs_root
        self.uploads_root = uploads_root
        self.exports_root = exports_root

        default_db_path = data_root / "app.db"
        self.database_url = get_setting(
            "DATABASE_URL",
            "AI_CONTENT_OPS_DATABASE_URL",
            default=f"sqlite:///{default_db_path.as_posix()}",
        )
        self.celery_broker_url = get_setting(
            "CELERY_BROKER_URL",
            "AI_CONTENT_OPS_CELERY_BROKER_URL",
            default="redis://127.0.0.1:6379/0",
        )
        self.celery_result_backend = get_setting(
            "CELERY_RESULT_BACKEND",
            "AI_CONTENT_OPS_CELERY_RESULT_BACKEND",
            default=self.celery_broker_url,
        )
        self.api_access_token = get_setting(
            "API_ACCESS_TOKEN",
            "AI_CONTENT_OPS_API_ACCESS_TOKEN",
            default=None,
        )
        self.auth_login_username = get_setting(
            "AUTH_LOGIN_USERNAME",
            "AI_CONTENT_OPS_AUTH_LOGIN_USERNAME",
            default=None,
        )
        self.auth_login_password = get_setting(
            "AUTH_LOGIN_PASSWORD",
            "AI_CONTENT_OPS_AUTH_LOGIN_PASSWORD",
            default=None,
        )
        self.auth_secret_key = get_setting(
            "AUTH_SECRET_KEY",
            "AI_CONTENT_OPS_AUTH_SECRET_KEY",
            default=None,
        )
        self.auth_token_ttl_minutes = int(
            get_setting(
                "AUTH_TOKEN_TTL_MINUTES",
                "AI_CONTENT_OPS_AUTH_TOKEN_TTL_MINUTES",
                default="480",
            )
            or "480"
        )
        self.auth_token_issuer = get_setting(
            "AUTH_TOKEN_ISSUER",
            "AI_CONTENT_OPS_AUTH_TOKEN_ISSUER",
            default="ai-content-ops",
        ) or "ai-content-ops"
        self.task_generation_provider = get_setting(
            "TASK_GENERATION_PROVIDER",
            "AI_CONTENT_OPS_TASK_GENERATION_PROVIDER",
            default="auto",
        ) or "auto"
        self.retrieval_profile_provider = get_setting(
            "RETRIEVAL_PROFILE_PROVIDER",
            "AI_CONTENT_OPS_RETRIEVAL_PROFILE_PROVIDER",
            default="auto",
        ) or "auto"
        self.deepseek_api_key = get_setting(
            "DEEPSEEK_API_KEY",
            "AI_CONTENT_OPS_DEEPSEEK_API_KEY",
            default=None,
        )
        self.deepseek_api_base_url = get_setting(
            "DEEPSEEK_API_BASE_URL",
            "AI_CONTENT_OPS_DEEPSEEK_API_BASE_URL",
            default="https://api.deepseek.com",
        ) or "https://api.deepseek.com"
        self.deepseek_model = get_setting(
            "DEEPSEEK_MODEL",
            "AI_CONTENT_OPS_DEEPSEEK_MODEL",
            default="deepseek-v4-flash",
        ) or "deepseek-v4-flash"
        self.deepseek_timeout_seconds = float(
            get_setting(
                "DEEPSEEK_TIMEOUT_SECONDS",
                "AI_CONTENT_OPS_DEEPSEEK_TIMEOUT_SECONDS",
                default="45",
            )
            or "45"
        )
        self.retrieval_embedding_dimension = int(
            get_setting(
                "RETRIEVAL_EMBEDDING_DIMENSION",
                "AI_CONTENT_OPS_RETRIEVAL_EMBEDDING_DIMENSION",
                default="128",
            )
            or "128"
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
        self.cors_origin_regex = r"^https?://(127\.0\.0\.1|localhost):(41|51)\d{2}$"
        self.allow_inline_background_fallback = _parse_bool(
            get_setting(
                "ALLOW_INLINE_BACKGROUND_FALLBACK",
                "AI_CONTENT_OPS_ALLOW_INLINE_BACKGROUND_FALLBACK",
                default=None,
            ),
            default=self.database_url.startswith("sqlite"),
        )
        self.auth_mode = self._derive_auth_mode()
        self._validate_auth_settings()

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

    def _derive_auth_mode(self) -> str:
        has_password_login = all(
            (
                self.auth_login_username,
                self.auth_login_password,
                self.auth_secret_key,
            )
        )
        if has_password_login:
            return "password_login"
        if self.api_access_token:
            return "legacy_token"
        return "disabled"

    def _validate_auth_settings(self) -> None:
        configured_login_fields = {
            "AUTH_LOGIN_USERNAME": self.auth_login_username,
            "AUTH_LOGIN_PASSWORD": self.auth_login_password,
            "AUTH_SECRET_KEY": self.auth_secret_key,
        }
        partially_configured = [
            name
            for name, value in configured_login_fields.items()
            if value
        ]
        if partially_configured and len(partially_configured) != len(configured_login_fields):
            missing_fields = [
                name
                for name, value in configured_login_fields.items()
                if not value
            ]
            missing_summary = ", ".join(missing_fields)
            raise ValueError(
                "Password login requires AUTH_LOGIN_USERNAME, AUTH_LOGIN_PASSWORD, and "
                f"AUTH_SECRET_KEY. Missing: {missing_summary}."
            )

        if self.auth_mode == "password_login" and len(self.auth_secret_key or "") < 16:
            raise ValueError("AUTH_SECRET_KEY must be at least 16 characters long.")

        if self.auth_token_ttl_minutes <= 0:
            raise ValueError("AUTH_TOKEN_TTL_MINUTES must be greater than 0.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton after creating runtime dirs."""

    settings = Settings()
    settings.ensure_runtime_directories()
    return settings
