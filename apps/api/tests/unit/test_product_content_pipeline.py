from __future__ import annotations

import json
from pathlib import Path

import importlib
import pytest
from sqlmodel import Session, select

from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.task_repository import TaskRepository
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.task_pipeline_service import TaskPipelineService


def test_pipeline_service_generates_product_brief_and_multi_channel_copies(
    session: Session,
    tmp_path: Path,
) -> None:
    knowledge_repository = KnowledgeRepository(session)

    brand_file = tmp_path / "brand-tone.md"
    brand_file.write_text(
        "# 品牌语气规范\n\n"
        "强调真实体验，避免绝对化承诺。\n",
        encoding="utf-8",
    )
    platform_file = tmp_path / "xiaohongshu-guide.md"
    platform_file.write_text(
        "# 小红书种草表达\n\n"
        "突出场景感和真实使用感，不要堆砌生硬卖点。\n",
        encoding="utf-8",
    )

    brand_document = knowledge_repository.create_document(
        title="品牌语气规范",
        source_path=str(brand_file),
        source_type="brand_guide",
        domain="ecommerce",
    )
    platform_document = knowledge_repository.create_document(
        title="小红书种草表达",
        source_path=str(platform_file),
        source_type="platform_guide",
        domain="ecommerce",
    )
    index_service = KnowledgeIndexService(knowledge_repository)
    index_service.index_document(brand_document.id)
    index_service.index_document(platform_document.id)

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "清透防晒霜",
                    "category": "护肤",
                    "specifications": ["50ml", "SPF50+ PA++++"],
                    "price_range": "89-129元",
                    "core_selling_points": ["清爽不搓泥", "通勤补涂方便"],
                    "target_audience": "通勤女生",
                    "use_scenarios": ["夏季通勤", "户外补涂"],
                    "promotion_notes": "618 第二件半价",
                },
                "task_description": "生成电商卖点、详情页和小红书种草短文案。",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.status == "completed"
    assert processed_task.understanding is not None
    assert processed_task.understanding["target_audience"] == "通勤女生"
    assert processed_task.understanding["primary_value_points"]
    assert processed_task.retrieval_hits
    assert {item["title"] for item in processed_task.retrieval_hits} == {
        "品牌语气规范",
        "小红书种草表达",
    }
    assert processed_task.understanding["input_alerts"] == []
    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["selling_strategy"]["primary_angle"] == "清爽不搓泥"
    assert processed_task.workflow_result["selling_strategy"]["supporting_angles"] == ["通勤补涂方便"]
    assert processed_task.workflow_result["selling_strategy"]["scenario_focus"] == ["夏季通勤", "户外补涂"]
    assert processed_task.workflow_result["selling_strategy"]["expression_guardrails"]
    assert all("命中《" not in item for item in processed_task.workflow_result["selling_strategy"]["expression_guardrails"])
    assert "score" not in " ".join(processed_task.workflow_result["selling_strategy"]["expression_guardrails"]).lower()
    assert processed_task.workflow_result["evidence_used"]
    assert processed_task.workflow_result["context_summary"]["candidate_hit_count"] >= 2
    assert processed_task.workflow_result["context_summary"]["selected_hit_count"] == len(
        processed_task.workflow_result["evidence_used"]
    )
    assert processed_task.workflow_result["context_summary"]["weak_retrieval"] is True
    assert processed_task.workflow_result["selling_points_copy"]
    assert processed_task.workflow_result["detail_page_copy"]
    assert processed_task.workflow_result["social_seed_copy"]
    assert processed_task.workflow_result["risk_notes"]
    assert "当前没有命中足够具体的商品或类目事实资料，建议补充商品事实卡或类目资料后再复核。" in (
        processed_task.workflow_result["risk_notes"]
    )
    assert processed_task.workflow_result["applied_guidelines"]
    assert processed_task.approved_snapshot is not None
    assert processed_task.approved_snapshot["workflow_result"]["selling_points_copy"]


def test_pipeline_service_builds_compact_product_retrieval_query(
    session: Session,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_retrieve(self, query_text: str, *, top_k: int = 3, domain: str | None = None) -> list[dict[str, object]]:
        captured["query_text"] = query_text
        captured["top_k"] = top_k
        captured["domain"] = domain
        return []

    monkeypatch.setattr("app.services.task_pipeline_service.RetrievalService.retrieve", fake_retrieve)

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "黑咖啡浓缩液",
                    "category": "冲调饮品",
                    "specifications": ["30ml*7条", "冷水即溶"],
                    "price_range": "39-49元",
                    "core_selling_points": ["便携提神", "冷水即溶"],
                    "target_audience": "通勤族、学生党",
                    "use_scenarios": ["早八通勤", "午后犯困"],
                    "promotion_notes": "夏季提神专题",
                },
                "task_description": "生成小红书种草短文案和详情页文案，重点突出真实使用感。",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    processed_task = TaskPipelineService(lambda: Session(session.get_bind())).run_pipeline(task.id)

    assert processed_task.status == "completed"
    assert captured["domain"] == "ecommerce"
    assert captured["top_k"] == 4
    assert captured["query_text"] == (
        "商品 黑咖啡浓缩液\n"
        "类目 冲调饮品\n"
        "核心卖点 便携提神 冷水即溶\n"
        "目标人群 通勤族、学生党\n"
        "使用场景 早八通勤 午后犯困\n"
        "内容目标 小红书 种草 详情页 真实体验 使用感 场景感"
    )


def test_pipeline_service_surfaces_weak_product_input_as_visible_alerts(
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "洁面乳",
                    "category": "个护清洁",
                    "specifications": ["150g"],
                    "price_range": "",
                    "core_selling_points": ["温和清洁"],
                    "target_audience": "",
                    "use_scenarios": [],
                    "promotion_notes": "",
                },
                "task_description": "生成三类商品内容初稿。",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.understanding is not None
    assert processed_task.understanding["input_alerts"] == [
        "规格参数还可以补充更细。",
        "核心卖点信息偏少，建议补充至少两个明确卖点。",
        "目标人群信息较弱，建议补充更具体的使用对象。",
        "使用场景信息较弱，建议补充典型使用场景。",
    ]
    assert processed_task.workflow_result is not None
    assert "输入信息仍有缺口，当前结果更适合作为人工补写底稿。" in processed_task.workflow_result["risk_notes"]
    assert "当前没有命中足够具体的商品或类目事实资料，建议补充商品事实卡或类目资料后再复核。" in processed_task.workflow_result["risk_notes"]


def test_pipeline_service_passes_weak_retrieval_state_into_generation_context(
    session: Session,
) -> None:
    class SpyGenerationProvider:
        provider_name = "spy-provider"

        def __init__(self) -> None:
            self.captured_context: dict[str, object] | None = None

        def build_understanding(self, parsed_input: dict[str, object]) -> dict[str, object]:
            return {
                "summary": "信息较少，需要保守生成。",
                "target_audience": "泛用户",
                "use_scenarios": [],
                "primary_value_points": ["便携"],
            }

        def build_workflow(
            self,
            *,
            parsed_input: dict[str, object],
            understanding: dict[str, object],
            retrieval_hits: list[dict[str, object]],
            generation_context: dict[str, object],
        ) -> dict[str, object]:
            self.captured_context = generation_context
            return {
                "selling_points_copy": ["先保守描述便携体验。"],
                "detail_page_copy": "信息不足时先输出保守草稿。",
                "social_seed_copy": "先不放大没有证据支撑的表达。",
                "risk_notes": [],
                "applied_guidelines": [],
            }

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "黑咖啡浓缩液",
                    "category": "饮品",
                    "specifications": ["12条"],
                    "price_range": "",
                    "core_selling_points": ["便携"],
                    "target_audience": "",
                    "use_scenarios": [],
                    "promotion_notes": "",
                },
                "task_description": "生成种草和详情页初稿。",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    provider = SpyGenerationProvider()
    processed_task = TaskPipelineService(
        lambda: Session(session.get_bind()),
        generation_provider=provider,
    ).run_pipeline(task.id)

    assert provider.captured_context is not None
    assert provider.captured_context["retrieval_quality"]["weak_retrieval"] is True
    assert provider.captured_context["selected_hits"] == []
    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["context_summary"]["weak_retrieval"] is True


def test_pipeline_service_persists_success_diagnostics_for_product_requests(
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "宠物除味喷雾",
                    "category": "宠物清洁",
                    "specifications": ["喷雾型"],
                    "price_range": "29-39元",
                    "core_selling_points": ["去味", "日常家用"],
                    "target_audience": "养宠家庭",
                    "use_scenarios": ["猫砂盆附近", "沙发"],
                    "promotion_notes": "",
                },
                "task_description": "生成三类商品内容初稿。",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    processed_task = TaskPipelineService(lambda: Session(session.get_bind())).run_pipeline(task.id)

    assert processed_task.workflow_result is not None
    diagnostics = processed_task.workflow_result["diagnostics"]
    assert diagnostics["generation_provider"]
    assert diagnostics["retrieval_provider"]
    assert diagnostics["retrieval_query"]
    assert diagnostics["retrieval_top_k_requested"] == 4
    assert diagnostics["candidate_hit_count"] == len(processed_task.retrieval_hits)


def test_pipeline_service_sanitizes_placeholder_facts_from_product_output(
    session: Session,
) -> None:
    class PlaceholderProvider:
        provider_name = "placeholder-provider"

        def build_understanding(self, parsed_input: dict[str, object]) -> dict[str, object]:
            return {
                "summary": "一款便携挂脖小风扇。",
                "target_audience": "通勤人群",
                "use_scenarios": ["通勤地铁", "排队等车"],
                "primary_value_points": ["解放双手", "轻便挂脖"],
            }

        def build_workflow(
            self,
            *,
            parsed_input: dict[str, object],
            understanding: dict[str, object],
            retrieval_hits: list[dict[str, object]],
                generation_context: dict[str, object],
            ) -> dict[str, object]:
                return {
                    "selling_points_copy": [
                        "约180g轻量不压脖，挂戴无负担",
                        "解放双手，通勤排队都能吹到风",
                    ],
                    "detail_page_copy": "约180g轻量机身，挂脖更无负担。解放双手，通勤排队都能用。",
                    "social_seed_copy": "某材质机身很高级。通勤挂脖吹风真的方便。",
                    "risk_notes": [],
                    "applied_guidelines": [],
                }

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "便携挂脖小风扇",
                    "category": "便携小家电",
                    "specifications": ["三档风力", "USB充电", "可挂脖"],
                    "price_range": "49-69元",
                    "core_selling_points": ["解放双手", "轻便挂脖"],
                    "target_audience": "通勤人群",
                    "use_scenarios": ["通勤地铁", "排队等车"],
                    "promotion_notes": "",
                },
                "task_description": "生成电商卖点、详情页和种草文案。",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    processed_task = TaskPipelineService(
        lambda: Session(session.get_bind()),
        generation_provider=PlaceholderProvider(),
    ).run_pipeline(task.id)

    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["selling_points_copy"] == ["解放双手，通勤排队都能吹到风"]
    assert "180g" not in processed_task.workflow_result["detail_page_copy"]
    assert "某材质" not in processed_task.workflow_result["social_seed_copy"]
    assert any("占位" in note for note in processed_task.workflow_result["risk_notes"])


def test_pipeline_service_raises_when_model_output_is_off_topic(
    session: Session,
) -> None:
    class OffTopicProvider:
        provider_name = "off-topic-provider"

        def build_understanding(self, parsed_input: dict[str, object]) -> dict[str, object]:
            return {
                "summary": "这是一款面向怕热通勤人群的便携风扇。",
                "target_audience": "怕热通勤人群",
                "use_scenarios": ["夏季通勤", "地铁排队"],
                "primary_value_points": ["解放双手", "通勤排队也能吹到风"],
            }

        def build_workflow(
            self,
            *,
            parsed_input: dict[str, object],
            understanding: dict[str, object],
            retrieval_hits: list[dict[str, object]],
            generation_context: dict[str, object],
        ) -> dict[str, object]:
            return {
                "selling_points_copy": [
                    "Lightning-fast data transfer for your devices.",
                    "Braided cable design for long-term durability.",
                ],
                "detail_page_copy": "A high-speed Type-C cable for work and travel.",
                "social_seed_copy": "This cable is perfect for laptops and phones.",
                "risk_notes": [],
                "applied_guidelines": [],
            }

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
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
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    with pytest.raises(ValueError, match="偏离商品事实"):
        TaskPipelineService(
            lambda: Session(session.get_bind()),
            generation_provider=OffTopicProvider(),
        ).run_pipeline(task.id)

    audit_module = importlib.import_module("app.models.audit_log")
    AuditLog = audit_module.AuditLog
    audit_rows = list(session.exec(select(AuditLog)).all())
    assert audit_rows[-1].event_type == "pipeline_failed"
    assert audit_rows[-1].outcome == "failure"
    assert audit_rows[-1].details["failure_stage"] == "generating"
    assert "偏离商品事实" in str(audit_rows[-1].details["failure_reason"])


def test_pipeline_service_keeps_product_output_when_copy_mentions_product_identity_but_paraphrases_points(
    session: Session,
) -> None:
    class ProductNameOnlyProvider:
        provider_name = "product-name-provider"

        def build_understanding(self, parsed_input: dict[str, object]) -> dict[str, object]:
            return {
                "summary": "这是一款适合通勤提神的黑咖啡浓缩液。",
                "target_audience": "通勤族、学生党",
                "use_scenarios": ["早八通勤", "午后犯困"],
                "primary_value_points": ["便携提神", "冷水即溶"],
            }

        def build_workflow(
            self,
            *,
            parsed_input: dict[str, object],
            understanding: dict[str, object],
            retrieval_hits: list[dict[str, object]],
            generation_context: dict[str, object],
        ) -> dict[str, object]:
            return {
                "selling_points_copy": [
                    "黑咖啡浓缩液做成小袋随身装，上班路上想喝就能冲。",
                    "不用找热水也能快速安排一杯，日常节奏更顺。",
                ],
                "detail_page_copy": "这款黑咖啡浓缩液更适合通勤和复习时快速补一杯，表达上更强调方便和节奏感。",
                "social_seed_copy": "最近包里常备黑咖啡浓缩液，赶早八时直接冷水一冲就能续命。",
                "risk_notes": ["避免把提神写成医疗功效。"],
                "applied_guidelines": ["品牌语气规范"],
            }

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "黑咖啡浓缩液",
                    "category": "冲调饮品",
                    "specifications": ["30ml*7条", "冷水即溶"],
                    "price_range": "39-49元",
                    "core_selling_points": ["便携提神", "冷水即溶"],
                    "target_audience": "通勤族、学生党",
                    "use_scenarios": ["早八通勤", "午后犯困"],
                    "promotion_notes": "夏季提神专题",
                },
                "task_description": "生成卖点文案、详情页文案和种草短文案。",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    processed_task = TaskPipelineService(
        lambda: Session(session.get_bind()),
        generation_provider=ProductNameOnlyProvider(),
    ).run_pipeline(task.id)

    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["selling_points_copy"][0] == "黑咖啡浓缩液做成小袋随身装，上班路上想喝就能冲。"
    assert all("模型结果偏离商品事实" not in note for note in processed_task.workflow_result["risk_notes"])
