from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.settings import Settings
from app.services.generation_provider import (
    DeepSeekTaskGenerationProvider,
    build_task_generation_provider,
)


def test_build_task_generation_provider_requires_deepseek_key_without_mode_override(
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

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        build_task_generation_provider(Settings())


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


def test_deepseek_product_provider_includes_strict_grounding_rules_in_prompt() -> None:
    captured_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "selling_points_copy": ["先保守描述真实体验。"],
                                    "detail_page_copy": "只按输入商品事实生成。",
                                    "social_seed_copy": "不虚构不存在的产品信息。",
                                    "risk_notes": ["避免超出输入事实。"],
                                    "applied_guidelines": ["品牌语气规范"],
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

    provider.build_workflow(
        parsed_input={
            "source_kind": "product_request",
            "product_payload": {
                "name": "便携挂脖小风扇",
                "category": "小家电",
                "specifications": ["Type-C充电", "三档风力"],
                "price_range": "49-69元",
                "core_selling_points": ["解放双手", "通勤排队也能吹到风"],
                "target_audience": "怕热通勤人群",
                "use_scenarios": ["夏季通勤", "地铁排队"],
                "promotion_notes": "第二件九折",
            },
            "task_description": "生成电商卖点、详情页和小红书种草短文案。",
        },
        understanding={
            "summary": "这是一款面向怕热通勤人群的夏季便携小风扇。",
            "target_audience": "怕热通勤人群",
            "use_scenarios": ["夏季通勤", "地铁排队"],
            "primary_value_points": ["解放双手", "通勤排队也能吹到风"],
        },
        retrieval_hits=[
            {
                "source_id": "brand-tone-guide",
                "title": "品牌语气规范",
                "snippet": "强调真实体验，避免绝对化承诺。",
                "reason": "命中《品牌语气规范》；核心内容提到“强调真实体验，避免绝对化承诺”。",
            }
        ],
        generation_context={
            "sections": ["product_brief", "retrieval_evidence"],
            "selected_hits": [
                {
                    "source_id": "brand-tone-guide",
                    "title": "品牌语气规范",
                    "snippet": "强调真实体验，避免绝对化承诺。",
                    "reason": "命中《品牌语气规范》；核心内容提到“强调真实体验，避免绝对化承诺”。",
                }
            ],
            "duplicate_hits_removed": 0,
            "manual_checks": [],
            "quality_flags": [],
            "retrieval_quality": {
                "candidate_hit_count": 1,
                "selected_hit_count": 1,
                "weak_retrieval": False,
            },
        },
    )

    system_prompt = captured_request["payload"]["messages"][0]["content"]
    user_payload = json.loads(captured_request["payload"]["messages"][1]["content"])

    assert "do not invent" in system_prompt.lower()
    assert "product facts" in system_prompt.lower()
    assert "retrieval hits are constraints" in system_prompt.lower()
    assert "at least two" in system_prompt.lower()
    assert "core_selling_points" in system_prompt
    assert "use_scenarios" in system_prompt
    assert "must mention the product name" in system_prompt.lower()
    assert "must not focus mainly on price" in system_prompt.lower()
    assert user_payload["generation_context"]["retrieval_quality"]["weak_retrieval"] is False


def test_deepseek_product_understanding_falls_back_when_model_returns_empty_target_audience() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "这是一款便携型饮品产品。",
                                    "target_audience": "",
                                    "use_scenarios": [],
                                    "primary_value_points": ["便携"],
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
            "source_kind": "product_request",
            "product_payload": {
                "name": "黑咖啡浓缩液",
                "category": "饮品",
                "specifications": ["12条"],
                "price_range": "",
                "core_selling_points": ["便携"],
                "target_audience": "",
                "use_scenarios": [],
                "promotion_notes": "",
            },
            "task_description": "生成三类商品内容初稿。",
        }
    )

    assert result["target_audience"] == "未明确目标人群"


def test_deepseek_product_workflow_repairs_malformed_json_before_parsing() -> None:
    requests_seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requests_seen.append(payload)
        if len(requests_seen) == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"selling_points_copy":["先讲便携提神"],'
                                    '"detail_page_copy":"突出冷水即溶",'
                                    '"social_seed_copy":"通勤包里放两条就够",'
                                    '"risk_notes":["避免绝对化承诺"],'
                                    '"applied_guidelines":["品牌语气规范"]'
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
                                    "selling_points_copy": ["先讲便携提神"],
                                    "detail_page_copy": "突出冷水即溶和低负担。",
                                    "social_seed_copy": "通勤包里放两条，犯困时随手一冲。",
                                    "risk_notes": ["避免绝对化承诺"],
                                    "applied_guidelines": ["品牌语气规范"],
                                },
                                ensure_ascii=False,
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
            "source_kind": "product_request",
            "product_payload": {
                "name": "黑咖啡浓缩液",
                "category": "冲调饮品",
                "specifications": ["30ml*7条", "冷水即溶"],
                "price_range": "39-49元",
                "core_selling_points": ["便携提神", "冷水即溶"],
                "target_audience": "通勤族",
                "use_scenarios": ["早八通勤", "午后犯困"],
                "promotion_notes": "夏季提神专题",
            },
            "task_description": "生成卖点文案、详情页文案和种草短文案。",
        },
        understanding={
            "summary": "黑咖啡浓缩液，重点突出便携提神与冷水即溶。",
            "target_audience": "通勤族",
            "use_scenarios": ["早八通勤", "午后犯困"],
            "primary_value_points": ["便携提神", "冷水即溶"],
        },
        retrieval_hits=[],
        generation_context={
            "sections": ["product_brief"],
            "selected_hits": [],
            "duplicate_hits_removed": 0,
            "manual_checks": [],
            "quality_flags": [],
            "retrieval_quality": {
                "candidate_hit_count": 0,
                "selected_hit_count": 0,
                "weak_retrieval": True,
            },
        },
    )

    assert len(requests_seen) == 2
    assert result["selling_points_copy"] == ["先讲便携提神"]
    assert result["detail_page_copy"] == "突出冷水即溶和低负担。"
    assert requests_seen[1]["messages"][0]["content"].lower().find("repair malformed json") >= 0


def test_deepseek_product_workflow_raises_when_json_repair_still_fails() -> None:
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
                            "content": '{"selling_points_copy":["先讲便携提神"],"detail_page_copy":"'
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

    with pytest.raises(json.JSONDecodeError):
        provider.build_workflow(
            parsed_input={
                "source_kind": "product_request",
                "product_payload": {
                    "name": "黑咖啡浓缩液",
                    "category": "冲调饮品",
                    "specifications": ["30ml*7条", "冷水即溶"],
                    "price_range": "39-49元",
                    "core_selling_points": ["便携提神", "冷水即溶"],
                    "target_audience": "通勤族",
                    "use_scenarios": ["早八通勤", "午后犯困"],
                    "promotion_notes": "夏季提神专题",
                },
                "task_description": "生成卖点文案、详情页文案和种草短文案。",
            },
            understanding={
                "summary": "黑咖啡浓缩液，重点突出便携提神与冷水即溶。",
                "target_audience": "通勤族",
                "use_scenarios": ["早八通勤", "午后犯困"],
                "primary_value_points": ["便携提神", "冷水即溶"],
            },
            retrieval_hits=[],
            generation_context={
                "sections": ["product_brief"],
                "selected_hits": [],
                "duplicate_hits_removed": 0,
                "manual_checks": [],
                "quality_flags": [],
                "retrieval_quality": {
                    "candidate_hit_count": 0,
                    "selected_hit_count": 0,
                    "weak_retrieval": True,
                },
            },
        )

    assert request_count == 2
