from __future__ import annotations

import json
from unittest.mock import MagicMock

from sqlmodel import Session

from app.models.task import TaskStatus
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
    assert body["reference_context"][0]["source_id"] == "brand-tone-guide"
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
    assert payload["generated_content"]["selling_points_copy"]
    assert payload["generated_content"]["detail_page_copy"]
    assert payload["generated_content"]["social_seed_copy"]
