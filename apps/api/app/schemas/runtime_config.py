from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeConfigRead(BaseModel):
    env_file_path: str = Field(description="Absolute path to the repo-local env file used by this API process.")
    setup_required: bool = Field(description="Whether the local machine still needs model configuration before the main chain can run.")
    deepseek_configured: bool = Field(description="Whether a DeepSeek API key is currently available to the main chain.")
    deepseek_api_base_url: str = Field(description="Resolved DeepSeek base URL used by the current runtime.")
    deepseek_model: str = Field(description="Resolved DeepSeek model name used by the current runtime.")
    task_generation_provider: str = Field(description="Current task generation provider mode.")
    retrieval_profile_provider: str = Field(description="Current retrieval profile provider mode.")
    missing_required_settings: list[str] = Field(description="Missing settings that still block the formal chain.")


class RuntimeConfigUpdate(BaseModel):
    deepseek_api_key: str = Field(min_length=1, description="Local DeepSeek API key written into apps/api/.env.local.")
    deepseek_api_base_url: str | None = Field(
        default=None,
        description="Optional DeepSeek base URL override for compatible gateways.",
    )
    deepseek_model: str | None = Field(
        default=None,
        description="Optional DeepSeek model override for the formal content chain.",
    )
