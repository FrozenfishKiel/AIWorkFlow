from pathlib import Path

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
