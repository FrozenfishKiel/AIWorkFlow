from __future__ import annotations

import json

from sqlmodel import Session

from app.repositories.task_repository import TaskRepository
from app.services.task_pipeline_service import TaskPipelineService


def test_pipeline_service_builds_product_request_retrieval_query_with_fact_signals(
    session: Session,
    monkeypatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_retrieve(self, query_text: str, *, top_k: int = 3, domain: str | None = None) -> list[dict[str, str]]:
        captured["query_text"] = query_text
        captured["domain"] = domain or ""
        return []

    monkeypatch.setattr(
        "app.services.retrieval_service.RetrievalService.retrieve",
        fake_retrieve,
    )

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(
            {
                "product": {
                    "name": "轻羽防晒喷雾",
                    "category": "防晒喷雾",
                    "specifications": ["50ml", "SPF50+", "PA++++"],
                    "price_range": "79-99元",
                    "core_selling_points": ["清爽不粘腻", "成膜快", "通勤补涂方便"],
                    "target_audience": "户外通勤女性",
                    "use_scenarios": ["夏季通勤", "户外补涂"],
                    "promotion_notes": "夏季上新",
                },
                "task_description": "帮我写一版更有种草感的小红书商品文案",
            },
            ensure_ascii=False,
        ),
        knowledge_domain="ecommerce",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.status == "completed"
    assert captured["domain"] == "ecommerce"
    assert "防晒喷雾" in captured["query_text"]
    assert "清爽不粘腻" in captured["query_text"]
    assert "成膜快" in captured["query_text"]
    assert "户外通勤女性" in captured["query_text"]
    assert "夏季通勤" in captured["query_text"]
    assert "小红书" in captured["query_text"]
    assert "种草" in captured["query_text"]
    assert "商品名称" not in captured["query_text"]
    assert "任务描述" not in captured["query_text"]
    assert "帮我写" not in captured["query_text"]
    assert "商品文案" not in captured["query_text"]
