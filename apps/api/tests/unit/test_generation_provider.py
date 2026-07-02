from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.settings import Settings
from app.services.generation_provider import (
    DeepSeekTaskGenerationProvider,
    DeterministicTaskGenerationProvider,
    build_task_generation_provider,
)


def test_build_task_generation_provider_defaults_to_deterministic_without_mode_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TASK_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("AI_CONTENT_OPS_TASK_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        "app.core.settings.derive_default_repo_root",
        lambda current_file=None: tmp_path,
    )

    provider = build_task_generation_provider(Settings())

    assert isinstance(provider, DeterministicTaskGenerationProvider)


def test_build_task_generation_provider_reads_repo_local_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apps_api_dir = tmp_path / "apps" / "api"
    apps_api_dir.mkdir(parents=True)
    (apps_api_dir / ".env.local").write_text(
        "TASK_GENERATION_PROVIDER=deepseek\n"
        "DEEPSEEK_API_KEY=test-key\n"
        "DEEPSEEK_MODEL=deepseek-v4-flash\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("TASK_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setattr(
        "app.core.settings.derive_default_repo_root",
        lambda current_file=None: tmp_path,
    )

    provider = build_task_generation_provider(Settings())

    assert isinstance(provider, DeepSeekTaskGenerationProvider)
    assert provider.model == "deepseek-v4-flash"
    assert provider.api_key == "test-key"


def test_deepseek_provider_requests_json_output_and_parses_response() -> None:
    captured_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["authorization"] = request.headers["Authorization"]
        captured_request["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Model summary",
                                    "audience": ["brand"],
                                    "key_points": ["Point A"],
                                    "risk_points": ["Risk A"],
                                    "uncertain_items": ["Question A"],
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com")
    provider = DeepSeekTaskGenerationProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )

    result = provider.build_understanding(
        {
            "source_kind": "text",
            "parsed_text": "Launch content that should stay grounded in evidence.",
            "input_quality": {
                "source_kind": "text",
                "quality_flags": [],
                "extracted_length": 58,
                "metadata": {},
            },
        }
    )

    assert result["summary"] == "Model summary"
    assert captured_request["url"] == "https://api.deepseek.com/chat/completions"
    assert captured_request["authorization"] == "Bearer test-key"
    assert captured_request["payload"]["response_format"] == {"type": "json_object"}
    assert captured_request["payload"]["model"] == "deepseek-v4-flash"
    assert "json" in captured_request["payload"]["messages"][0]["content"].lower()


def test_deepseek_provider_coerces_single_string_fields_into_lists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Model summary",
                                    "audience": "brand reviewer",
                                    "key_points": "Keep claims grounded.",
                                    "risk_points": "Evidence may be incomplete.",
                                    "uncertain_items": "CTA still needs review.",
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com")
    provider = DeepSeekTaskGenerationProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )

    result = provider.build_understanding(
        {
            "source_kind": "text",
            "parsed_text": "Launch content that should stay grounded in evidence.",
            "input_quality": {
                "source_kind": "text",
                "quality_flags": [],
                "extracted_length": 58,
                "metadata": {},
            },
        }
    )

    assert result["audience"] == ["brand reviewer"]
    assert result["key_points"] == ["Keep claims grounded."]
    assert result["risk_points"] == ["Evidence may be incomplete."]
    assert result["uncertain_items"] == ["CTA still needs review."]


def test_deepseek_provider_coerces_draft_list_into_plain_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "draft": [
                                        "Launch messaging should stay practical.",
                                        "Visible citations must remain attached.",
                                    ],
                                    "review_notes": "Double-check the CTA.",
                                    "open_questions": [],
                                    "manual_checks": "Verify every cited claim.",
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com")
    provider = DeepSeekTaskGenerationProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )

    result = provider.build_workflow(
        parsed_input={
            "source_kind": "text",
            "parsed_text": "Create launch messaging with visible citations.",
            "input_quality": {
                "source_kind": "text",
                "quality_flags": [],
                "extracted_length": 47,
                "metadata": {},
            },
        },
        understanding={
            "summary": "Launch messaging task.",
            "audience": ["brand"],
            "key_points": ["Keep citations visible."],
            "risk_points": [],
            "uncertain_items": [],
        },
        retrieval_hits=[],
        generation_context={
            "sections": ["task_goal"],
            "selected_hits": [],
            "duplicate_hits_removed": 0,
            "manual_checks": [],
            "quality_flags": [],
        },
    )

    assert result["draft"] == (
        "Launch messaging should stay practical.\nVisible citations must remain attached."
    )
    assert result["review_notes"] == ["Double-check the CTA."]
    assert result["manual_checks"] == ["Verify every cited claim."]
