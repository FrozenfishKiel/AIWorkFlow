from __future__ import annotations

import json
from unittest.mock import MagicMock

from sqlmodel import Session

from app.models import AuditEventType, AuditOutcome, TaskStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository
from app.services.task_pipeline_service import TaskPipelineService


def build_product_payload() -> dict[str, object]:
    return {
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
    }


def test_create_product_content_job_returns_queued_generation_job(
    client,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_product_content.run_task_pipeline.delay", enqueue_mock)

    response = client.post("/product-content/jobs", json=build_product_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == TaskStatus.QUEUED
    assert payload["product"]["name"] == "清透防晒霜"
    assert payload["product"]["category"] == "护肤"
    assert payload["task_description"] == "生成电商卖点、详情页和小红书种草短文案。"
    assert payload["generated_content"] is None
    enqueue_mock.assert_called_once_with(payload["id"])


def test_get_product_content_job_returns_generated_ecommerce_outputs(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    payload = build_product_payload()
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(payload, ensure_ascii=False),
    )
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "这是一款面向通勤女生的夏季防晒产品，重点突出清爽肤感和补涂便利性。",
            "target_audience": "通勤女生",
            "use_scenarios": ["夏季通勤", "户外补涂"],
            "primary_value_points": ["清爽不搓泥", "补涂方便", "高倍防护"],
            "input_alerts": [],
        },
        retrieval_hits=[
            {
                "source_id": "brand-tone-guide",
                "title": "品牌语气规范",
                "snippet": "强调真实体验，不要使用绝对化承诺。",
                "reason": "约束种草文案表达方式。",
            }
        ],
        workflow_result={
            "selling_strategy": {
                "primary_angle": "清爽不搓泥",
                "supporting_angles": ["补涂方便", "高倍防护"],
                "scenario_focus": ["夏季通勤", "户外补涂"],
                "expression_guardrails": ["避免绝对化表达", "优先强调真实肤感"],
            },
            "evidence_used": [
                {
                    "source_id": "brand-tone-guide",
                    "title": "品牌语气规范",
                    "snippet": "强调真实体验，不要使用绝对化承诺。",
                    "reason": "命中《品牌语气规范》；核心内容提到“强调真实体验，不要使用绝对化承诺”。",
                }
            ],
            "context_summary": {
                "candidate_hit_count": 1,
                "selected_hit_count": 1,
                "weak_retrieval": False,
            },
            "selling_points_copy": [
                "轻薄成膜，通勤补涂不黏腻。",
                "高倍防护覆盖日常通勤与户外短时活动。",
            ],
            "detail_page_copy": "这款防晒霜主打轻透肤感与高倍防护，适合夏季通勤和外出补涂场景。",
            "social_seed_copy": "通勤女孩真的会反复回购这支，补涂不搓泥，包里常备很安心。",
            "risk_notes": ["避免使用“24小时绝对防晒”这类夸张表达。"],
            "applied_guidelines": ["品牌语气规范"],
        },
    )

    response = client.get(f"/product-content/jobs/{task.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["product"]["name"] == "清透防晒霜"
    assert body["product_brief"]["target_audience"] == "通勤女生"
    assert body["product_brief"]["primary_value_points"] == ["清爽不搓泥", "补涂方便", "高倍防护"]
    assert body["selling_strategy"]["primary_angle"] == "清爽不搓泥"
    assert body["selling_strategy"]["supporting_angles"] == ["补涂方便", "高倍防护"]
    assert body["input_alerts"] == []
    assert body["reference_context"][0]["source_id"] == "brand-tone-guide"
    assert body["retrieval_candidates"][0]["source_id"] == "brand-tone-guide"
    assert body["context_summary"]["selected_hit_count"] == 1
    assert body["diagnostics"] is None
    assert body["generated_content"]["selling_points_copy"][0] == "轻薄成膜，通勤补涂不黏腻。"
    assert body["generated_content"]["detail_page_copy"].startswith("这款防晒霜主打轻透肤感")
    assert "绝对防晒" in body["generated_content"]["risk_notes"][0]


def test_create_product_content_job_runs_inline_when_queue_is_unavailable(
    client,
    monkeypatch,
) -> None:
    def raise_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr("app.api.routes_product_content.run_task_pipeline.delay", raise_enqueue)

    response = client.post("/product-content/jobs", json=build_product_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == TaskStatus.COMPLETED
    assert payload["product_brief"]["summary"]
    assert payload["selling_strategy"]["primary_angle"]
    assert isinstance(payload["input_alerts"], list)
    assert payload["generated_content"]["selling_points_copy"]
    assert payload["generated_content"]["detail_page_copy"]
    assert payload["generated_content"]["social_seed_copy"]


def test_create_product_content_job_returns_failed_job_payload_when_inline_formal_chain_fails(
    client,
    monkeypatch,
) -> None:
    def raise_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr("app.api.routes_product_content.run_task_pipeline.delay", raise_enqueue)
    monkeypatch.setattr(
        "app.services.task_pipeline_service.TaskPipelineService._product_workflow_looks_off_topic",
        lambda *args, **kwargs: True,
    )

    response = client.post("/product-content/jobs", json=build_product_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == TaskStatus.FAILED
    assert "偏离商品事实" in str(payload["error_message"])
    assert payload["diagnostics"]["failure_stage"] == "generating"
    assert "偏离商品事实" in str(payload["diagnostics"]["failure_reason"])


def test_legacy_tasks_routes_are_not_public_anymore(client) -> None:
    legacy_endpoints = [
        client.get("/tasks"),
        client.post("/tasks", json={"input_type": "text", "content": "legacy"}),
        client.post(
            "/tasks/upload",
            files={"file": ("legacy.md", b"# legacy", "text/markdown")},
        ),
    ]

    assert [response.status_code for response in legacy_endpoints] == [404, 404, 404]


def test_product_content_job_audit_logs_are_available_from_formal_entry(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(build_product_payload(), ensure_ascii=False),
        knowledge_domain="ecommerce",
    )
    TaskPipelineService(lambda: Session(session.get_bind())).run_pipeline(task.id)

    response = client.get(f"/product-content/jobs/{task.id}/audit-logs")

    assert response.status_code == 200
    payload = response.json()
    assert [item["event_type"] for item in payload] == [
        "snapshot_persisted",
        "pipeline_completed",
    ]
    assert payload[0]["task_id"] == str(task.id)
    assert payload[0]["summary"]


def test_get_product_content_job_surfaces_failure_diagnostics_from_audit_log(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    audit_repository = AuditLogRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(build_product_payload(), ensure_ascii=False),
        knowledge_domain="ecommerce",
    )
    repository.update_status(
        task=task,
        status=TaskStatus.FAILED,
        error_message="模型输出偏离商品事实，已终止当前任务。",
    )
    audit_repository.create_log(
        task_id=task.id,
        event_type=AuditEventType.PIPELINE_FAILED,
        outcome=AuditOutcome.FAILURE,
        summary="Pipeline failed before a stable result could be persisted.",
        details={
            "generation_provider": "deepseek",
            "retrieval_provider": "deepseek-retrieval-profile",
            "retrieval_query": "商品 清透防晒霜",
            "retrieval_top_k_requested": 4,
            "retrieval_top_k_effective": 2,
            "candidate_hit_count": 2,
            "selected_hit_count": 0,
            "selected_source_ids": [],
            "selected_titles": [],
            "weak_retrieval": True,
            "duplicate_hits_removed": 0,
            "failure_stage": "generating",
            "failure_reason": "模型输出偏离商品事实，已终止当前任务。",
        },
    )

    response = client.get(f"/product-content/jobs/{task.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_message"] == "模型输出偏离商品事实，已终止当前任务。"
    assert payload["diagnostics"]["generation_provider"] == "deepseek"
    assert payload["diagnostics"]["retrieval_provider"] == "deepseek-retrieval-profile"
    assert payload["diagnostics"]["failure_stage"] == "generating"
    assert payload["diagnostics"]["failure_reason"] == "模型输出偏离商品事实，已终止当前任务。"
