from __future__ import annotations

import json

import httpx
import pytest

from app.core.settings import Settings
from app.services.retrieval_profile_provider import (
    DeepSeekRetrievalProfileProvider,
    build_retrieval_profile_provider,
)


def test_build_retrieval_profile_provider_requires_deepseek_key_without_mode_override(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RETRIEVAL_PROFILE_PROVIDER", raising=False)
    monkeypatch.delenv("AI_CONTENT_OPS_RETRIEVAL_PROFILE_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        "app.core.settings.derive_default_repo_root",
        lambda current_file=None: tmp_path,
    )

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        build_retrieval_profile_provider(Settings())


def test_deepseek_retrieval_profile_provider_repairs_malformed_json() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"retrieval_text":"便携提神 黑咖啡浓缩液",'
                                    '"keywords":["便携提神","黑咖啡"],'
                                    '"synonyms":["浓缩咖啡"],'
                                    '"constraints":["ecommerce"]'
                                )
                            }
                        }
                    ]
                },
            )

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "retrieval_text": "便携提神 黑咖啡浓缩液",
                                    "keywords": ["便携提神", "黑咖啡"],
                                    "synonyms": ["浓缩咖啡"],
                                    "constraints": ["ecommerce"],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com")
    provider = DeepSeekRetrievalProfileProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )

    result = provider.build_query_profile(query_text="黑咖啡浓缩液 便携提神", domain="ecommerce")

    assert request_count == 2
    assert result["keywords"] == ["便携提神", "黑咖啡"]


def test_deepseek_retrieval_profile_provider_raises_when_repair_still_fails() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"retrieval_text":"黑咖啡浓缩液",'
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com")
    provider = DeepSeekRetrievalProfileProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )

    with pytest.raises(json.JSONDecodeError):
        provider.build_query_profile(query_text="黑咖啡浓缩液 便携提神", domain="ecommerce")

    assert request_count == 2
