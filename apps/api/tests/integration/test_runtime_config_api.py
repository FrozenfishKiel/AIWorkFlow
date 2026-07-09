from __future__ import annotations

from pathlib import Path

import pytest

from app.core.settings import get_settings


@pytest.fixture()
def isolated_runtime_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    apps_api_dir = tmp_path / "apps" / "api"
    apps_api_dir.mkdir(parents=True)

    for env_name in (
        "DEEPSEEK_API_KEY",
        "AI_CONTENT_OPS_DEEPSEEK_API_KEY",
        "DEEPSEEK_API_BASE_URL",
        "AI_CONTENT_OPS_DEEPSEEK_API_BASE_URL",
        "DEEPSEEK_MODEL",
        "AI_CONTENT_OPS_DEEPSEEK_MODEL",
    ):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setattr(
        "app.core.settings.derive_default_repo_root",
        lambda current_file=None: tmp_path,
    )
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_runtime_config_reports_when_local_model_setup_is_missing(
    client,
    isolated_runtime_repo: Path,
) -> None:
    response = client.get("/runtime-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["setup_required"] is True
    assert payload["deepseek_configured"] is False
    assert payload["missing_required_settings"] == ["DEEPSEEK_API_KEY"]
    assert payload["deepseek_api_base_url"] == "https://api.deepseek.com"
    assert payload["deepseek_model"] == "deepseek-v4-flash"
    assert payload["env_file_path"].replace("\\", "/").endswith("apps/api/.env.local")


def test_runtime_config_persists_local_deepseek_settings_without_echoing_secret(
    client,
    isolated_runtime_repo: Path,
) -> None:
    response = client.put(
        "/runtime-config",
        json={
            "deepseek_api_key": "sk-test-123",
            "deepseek_api_base_url": "https://api.deepseek.com",
            "deepseek_model": "deepseek-chat",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["setup_required"] is False
    assert payload["deepseek_configured"] is True
    assert payload["missing_required_settings"] == []
    assert "deepseek_api_key" not in payload

    env_file = isolated_runtime_repo / "apps" / "api" / ".env.local"
    assert env_file.exists() is True
    env_text = env_file.read_text(encoding="utf-8")
    assert 'DEEPSEEK_API_KEY="sk-test-123"' in env_text
    assert 'DEEPSEEK_MODEL="deepseek-chat"' in env_text

    follow_up = client.get("/runtime-config")
    assert follow_up.status_code == 200
    assert follow_up.json()["deepseek_model"] == "deepseek-chat"
