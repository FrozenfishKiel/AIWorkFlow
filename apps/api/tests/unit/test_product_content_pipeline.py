from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

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
    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["selling_points_copy"]
    assert processed_task.workflow_result["detail_page_copy"]
    assert processed_task.workflow_result["social_seed_copy"]
    assert processed_task.workflow_result["risk_notes"]
    assert processed_task.workflow_result["applied_guidelines"]
    assert processed_task.approved_snapshot is not None
    assert processed_task.approved_snapshot["workflow_result"]["selling_points_copy"]
