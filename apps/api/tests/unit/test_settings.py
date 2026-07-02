from pathlib import Path

import pytest

from app.core.settings import derive_default_repo_root, Settings


def test_derive_default_repo_root_supports_container_style_paths() -> None:
    current_file = Path("/app/app/core/settings.py")

    assert derive_default_repo_root(current_file) == Path("/app")


def test_settings_prefers_explicit_runtime_and_service_environment_variables(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"

    monkeypatch.setenv("AI_CONTENT_OPS_RUNTIME_DIR", str(runtime_root))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

    settings = Settings()

    assert settings.runtime_root == runtime_root
    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/app"
    assert settings.celery_broker_url == "redis://redis:6379/0"
    assert settings.celery_result_backend == "redis://redis:6379/1"


def test_settings_enable_password_login_mode_when_operator_credentials_are_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUTH_LOGIN_USERNAME", "operator")
    monkeypatch.setenv("AUTH_LOGIN_PASSWORD", "open-sesame")
    monkeypatch.setenv("AUTH_SECRET_KEY", "0123456789abcdef0123456789abcdef")

    settings = Settings()

    assert settings.auth_mode == "password_login"
    assert settings.auth_login_username == "operator"
    assert settings.auth_token_ttl_minutes > 0


def test_settings_allow_local_vite_ports_for_cors() -> None:
    settings = Settings()

    assert settings.cors_origin_regex == r"^https?://(127\.0\.0\.1|localhost):51\d{2}$"


def test_settings_reject_partial_password_login_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUTH_LOGIN_USERNAME", "operator")
    monkeypatch.setenv("AUTH_LOGIN_PASSWORD", "open-sesame")
    monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)

    with pytest.raises(ValueError, match="AUTH_SECRET_KEY"):
        Settings()
