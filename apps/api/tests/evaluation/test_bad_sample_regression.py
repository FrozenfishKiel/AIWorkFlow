from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session

from app.repositories.task_repository import TaskRepository
from app.services.task_pipeline_service import TaskPipelineService


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "bad_product_samples.json"


def _load_bad_samples() -> list[dict[str, object]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("case_id", "payload", "expected"),
    [
        pytest.param(case["case_id"], case["payload"], case["expected"], id=str(case["case_id"]))
        for case in _load_bad_samples()
    ],
)
def test_bad_product_samples_keep_weak_retrieval_visible_and_outputs_conservative(
    session: Session,
    case_id: str,
    payload: dict[str, object],
    expected: dict[str, object],
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(payload, ensure_ascii=False),
        knowledge_domain="ecommerce",
    )

    processed_task = TaskPipelineService(lambda: Session(session.get_bind())).run_pipeline(task.id)

    assert processed_task.status == "completed", case_id
    assert processed_task.understanding is not None
    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["context_summary"]["selected_hit_count"] == expected["selected_hit_count"]
    assert processed_task.workflow_result["context_summary"]["weak_retrieval"] is expected["weak_retrieval"]

    input_alerts = processed_task.understanding["input_alerts"]
    risk_notes = processed_task.workflow_result["risk_notes"]

    for snippet in expected["input_alert_contains"]:
        assert any(snippet in item for item in input_alerts), f"{case_id}: missing input alert snippet {snippet!r}"

    for snippet in expected["risk_note_contains"]:
        assert any(snippet in item for item in risk_notes), f"{case_id}: missing risk note snippet {snippet!r}"
