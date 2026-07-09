from __future__ import annotations

from fastapi import APIRouter

from app.core.settings import get_settings, write_local_env_file
from app.schemas.runtime_config import RuntimeConfigRead, RuntimeConfigUpdate

router = APIRouter(prefix="/runtime-config", tags=["runtime-config"])


def _build_runtime_config_response() -> RuntimeConfigRead:
    settings = get_settings()
    missing_required_settings: list[str] = []
    if not settings.deepseek_api_key:
        missing_required_settings.append("DEEPSEEK_API_KEY")

    return RuntimeConfigRead(
        env_file_path=str(settings.local_env_file),
        setup_required=bool(missing_required_settings),
        deepseek_configured=not missing_required_settings,
        deepseek_api_base_url=settings.deepseek_api_base_url,
        deepseek_model=settings.deepseek_model,
        task_generation_provider=settings.task_generation_provider,
        retrieval_profile_provider=settings.retrieval_profile_provider,
        missing_required_settings=missing_required_settings,
    )


@router.get("", response_model=RuntimeConfigRead)
def get_runtime_config() -> RuntimeConfigRead:
    """Expose the local model setup state for first-run project bootstrapping."""

    return _build_runtime_config_response()


@router.put("", response_model=RuntimeConfigRead)
def update_runtime_config(payload: RuntimeConfigUpdate) -> RuntimeConfigRead:
    """Persist local model settings into the repo-local env file for this machine."""

    settings = get_settings()
    write_local_env_file(
        settings.local_env_file,
        {
            "DEEPSEEK_API_KEY": payload.deepseek_api_key,
            "DEEPSEEK_API_BASE_URL": payload.deepseek_api_base_url or "https://api.deepseek.com",
            "DEEPSEEK_MODEL": payload.deepseek_model or "deepseek-v4-flash",
        },
    )
    get_settings.cache_clear()
    return _build_runtime_config_response()
