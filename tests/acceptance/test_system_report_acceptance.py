from __future__ import annotations

import json

from sqlmodel import Session

from app.models import AuditEventType, AuditOutcome, ExportJobStatus, TaskStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository


def build_product_payload() -> dict[str, object]:
    return {
        "product": {
            "name": "氨基酸净澈洁面乳",
            "category": "个护清洁",
            "specifications": ["150g", "氨基酸配方", "敏感肌可用"],
            "price_range": "79-99元",
            "core_selling_points": ["温和净润", "泡沫细腻", "清洁后不紧绷"],
            "target_audience": "18-35岁女性",
            "use_scenarios": ["日常洁面", "换季维稳", "早晚护肤"],
            "promotion_notes": "夏季焕肤专题，主打温和净澈",
        },
        "task_description": "生成电商卖点文案、详情页文案和小红书种草短文案。",
    }


def _build_report_entry(
    *,
    scenario: str,
    job: dict[str, object],
    export_status: str,
) -> dict[str, object]:
    diagnostics = dict(job.get("diagnostics") or {})
    return {
        "scenario": scenario,
        "provider": diagnostics.get("generation_provider"),
        "top_k": diagnostics.get("retrieval_top_k_requested"),
        "selected_hits": diagnostics.get("selected_titles"),
        "weak_retrieval": diagnostics.get("weak_retrieval"),
        "final_status": job["status"],
        "export_status": export_status,
        "failure_reason": diagnostics.get("failure_reason"),
    }


def test_system_report_acceptance_captures_success_and_failure_rows(
    client,
    engine,
    monkeypatch,
) -> None:
    def raise_task_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    def raise_export_enqueue(*args, **kwargs):
        raise RuntimeError("export broker unavailable")

    monkeypatch.setattr("app.api.routes_product_content.run_task_pipeline.delay", raise_task_enqueue)
    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", raise_export_enqueue)

    success_create_response = client.post("/product-content/jobs", json=build_product_payload())
    assert success_create_response.status_code == 201
    success_job = success_create_response.json()

    success_export_response = client.post(
        "/exports",
        json={
            "task_id": success_job["id"],
            "export_type": "markdown",
        },
    )
    assert success_export_response.status_code == 201
    success_export_job = success_export_response.json()

    with Session(engine) as session:
        repository = TaskRepository(session)
        audit_repository = AuditLogRepository(session)
        failed_task = repository.create_task(
            input_type="product_request",
            content=json.dumps(build_product_payload(), ensure_ascii=False),
            knowledge_domain="ecommerce",
        )
        repository.update_status(
            task=failed_task,
            status=TaskStatus.FAILED,
            error_message="模型输出偏离商品事实，已终止当前任务。",
        )
        audit_repository.create_log(
            task_id=failed_task.id,
            event_type=AuditEventType.PIPELINE_FAILED,
            outcome=AuditOutcome.FAILURE,
            summary="Pipeline failed after retrieval completed.",
            details={
                "generation_provider": "fake-deepseek-acceptance-provider",
                "retrieval_provider": "fake-deepseek-acceptance-retrieval-profile",
                "retrieval_query": "商品 氨基酸净澈洁面乳",
                "retrieval_top_k_requested": 4,
                "retrieval_top_k_effective": 1,
                "candidate_hit_count": 1,
                "selected_hit_count": 0,
                "selected_source_ids": [],
                "selected_titles": [],
                "weak_retrieval": True,
                "duplicate_hits_removed": 0,
                "failure_stage": "generating",
                "failure_reason": "模型输出偏离商品事实，已终止当前任务。",
            },
        )
        failed_task_id = failed_task.id

    failed_response = client.get(f"/product-content/jobs/{failed_task_id}")
    assert failed_response.status_code == 200
    failed_job = failed_response.json()

    report_rows = [
        _build_report_entry(
            scenario="success_with_export",
            job=success_job,
            export_status=success_export_job["status"],
        ),
        _build_report_entry(
            scenario="failure_without_export",
            job=failed_job,
            export_status="skipped",
        ),
    ]

    success_row = report_rows[0]
    assert success_row == {
        "scenario": "success_with_export",
        "provider": "fake-deepseek-acceptance-provider",
        "top_k": 4,
        "selected_hits": success_job["diagnostics"]["selected_titles"],
        "weak_retrieval": False,
        "final_status": TaskStatus.COMPLETED,
        "export_status": ExportJobStatus.COMPLETED,
        "failure_reason": None,
    }
    assert success_row["selected_hits"]

    failure_row = report_rows[1]
    assert failure_row == {
        "scenario": "failure_without_export",
        "provider": "fake-deepseek-acceptance-provider",
        "top_k": 4,
        "selected_hits": [],
        "weak_retrieval": True,
        "final_status": TaskStatus.FAILED,
        "export_status": "skipped",
        "failure_reason": "模型输出偏离商品事实，已终止当前任务。",
    }
