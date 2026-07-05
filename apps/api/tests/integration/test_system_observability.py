from __future__ import annotations

import json

from sqlmodel import Session

from app.models import AuditEventType, AuditOutcome, TaskStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository


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


def test_duplicate_product_content_submissions_create_distinct_jobs(
    client,
    monkeypatch,
) -> None:
    def raise_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr("app.api.routes_product_content.run_task_pipeline.delay", raise_enqueue)

    first_response = client.post("/product-content/jobs", json=build_product_payload())
    second_response = client.post("/product-content/jobs", json=build_product_payload())

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_job = first_response.json()
    second_job = second_response.json()

    assert first_job["id"] != second_job["id"]
    assert first_job["status"] == TaskStatus.COMPLETED
    assert second_job["status"] == TaskStatus.COMPLETED
    assert first_job["product"] == second_job["product"]
    assert first_job["task_description"] == second_job["task_description"]
    assert first_job["generated_content"]["selling_points_copy"]
    assert second_job["generated_content"]["selling_points_copy"]


def test_failed_product_content_job_exposes_diagnostics_and_failure_reason(
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
        summary="Pipeline failed after retrieval diagnostics were captured.",
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
            "duplicate_hits_removed": 1,
            "failure_stage": "generating",
            "failure_reason": "模型输出偏离商品事实，已终止当前任务。",
        },
    )

    response = client.get(f"/product-content/jobs/{task.id}")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == TaskStatus.FAILED
    assert payload["error_message"] == "模型输出偏离商品事实，已终止当前任务。"
    assert payload["generated_content"] is None
    assert payload["reference_context"] == []
    assert payload["retrieval_candidates"] == []
    assert payload["diagnostics"] == {
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
        "duplicate_hits_removed": 1,
        "failure_stage": "generating",
        "failure_reason": "模型输出偏离商品事实，已终止当前任务。",
    }
