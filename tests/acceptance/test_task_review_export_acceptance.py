from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.models import ExportJobStatus, KnowledgeDocumentStatus, TaskStatus
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.task_repository import TaskRepository
from app.services.export_service import ExportService
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.task_pipeline_service import TaskPipelineService


def test_root_acceptance_covers_index_task_review_and_export(
    client,
    engine,
    runtime_dir: Path,
    monkeypatch,
    tmp_path: Path,
) -> None:
    knowledge_source = tmp_path / "brand-guideline.md"
    knowledge_source.write_text(
        "# Brand guideline\n\n"
        "Keep citations visible for every reviewer.\n\n"
        "Human review is required before export.\n\n"
        "Content ops teams need grounded launch messaging.\n",
        encoding="utf-8",
    )

    index_enqueue_calls: list[str] = []
    task_enqueue_calls: list[str] = []
    export_enqueue_calls: list[str] = []

    monkeypatch.setattr(
        "app.api.routes_knowledge.index_knowledge_document.delay",
        lambda document_id: index_enqueue_calls.append(document_id),
    )
    monkeypatch.setattr(
        "app.api.routes_tasks.run_task_pipeline.delay",
        lambda task_id: task_enqueue_calls.append(task_id),
    )
    monkeypatch.setattr(
        "app.api.routes_exports.run_export_job.delay",
        lambda export_job_id: export_enqueue_calls.append(export_job_id),
    )

    knowledge_response = client.post(
        "/knowledge/index-local",
        json={
            "title": "Brand guideline",
            "source_path": str(knowledge_source),
            "source_type": "brand_guideline",
            "domain": "brand",
        },
    )

    assert knowledge_response.status_code == 201
    knowledge_document = knowledge_response.json()
    assert knowledge_document["status"] == KnowledgeDocumentStatus.QUEUED
    assert index_enqueue_calls == [knowledge_document["id"]]

    with Session(engine) as session:
        indexed_document = KnowledgeIndexService(KnowledgeRepository(session)).index_document(knowledge_document["id"])
        chunks = KnowledgeRepository(session).list_chunks_for_document(indexed_document.id)

    assert indexed_document.status == KnowledgeDocumentStatus.INDEXED
    assert indexed_document.chunk_count >= 1
    assert any("citations visible" in chunk.content for chunk in chunks)

    create_task_response = client.post(
        "/tasks",
        json={
            "input_type": "text",
            "content": "Create launch messaging for content ops teams with visible citations before export.",
        },
    )

    assert create_task_response.status_code == 201
    created_task = create_task_response.json()
    assert created_task["status"] == TaskStatus.QUEUED
    assert task_enqueue_calls == [created_task["id"]]

    with Session(engine) as session:
        processed_task = TaskPipelineService(lambda: Session(engine)).run_pipeline(created_task["id"])

    assert processed_task.status == TaskStatus.REVIEW_PENDING
    assert processed_task.understanding is not None
    assert processed_task.workflow_result is not None
    assert processed_task.retrieval_hits
    assert processed_task.retrieval_hits[0]["title"] == "Brand guideline"
    assert "citations visible" in processed_task.retrieval_hits[0]["snippet"].lower()

    start_review_response = client.post(f"/reviews/{created_task['id']}/start")

    assert start_review_response.status_code == 200
    assert start_review_response.json()["status"] == TaskStatus.REVIEWING

    approve_payload = {
        "edited_understanding": {
            "summary": "Approved summary with reviewer edits.",
            "audience": ["content-ops", "brand"],
            "key_points": [
                "Keep citations visible for reviewers.",
                "Require human approval before export.",
            ],
        },
        "edited_retrieval_hits": [
            {
                "source_id": processed_task.retrieval_hits[0]["source_id"],
                "title": processed_task.retrieval_hits[0]["title"],
                "snippet": processed_task.retrieval_hits[0]["snippet"],
                "reason": "Reviewer kept the indexed brand source because it supports the approval gate.",
            }
        ],
        "edited_workflow_result": {
            "draft": "Reviewed launch draft with visible citations and an explicit review gate.",
            "review_notes": ["Approved for markdown export."],
            "open_questions": ["Should legal also review campaign claims?"],
        },
        "not_adopted_items": ["Dropped any unsupported launch-performance claim."],
        "reviewer_note": "Approved after keeping only attributed guidance.",
    }

    approve_response = client.post(f"/reviews/{created_task['id']}/approve", json=approve_payload)

    assert approve_response.status_code == 200
    approved_task = approve_response.json()
    assert approved_task["status"] == TaskStatus.APPROVED
    assert approved_task["approved_snapshot"]["workflow_result"]["draft"] == (
        "Reviewed launch draft with visible citations and an explicit review gate."
    )
    assert approved_task["approved_snapshot"]["retrieval_hits"][0]["title"] == "Brand guideline"

    create_export_response = client.post(
        "/exports",
        json={
            "task_id": created_task["id"],
            "export_type": "markdown",
        },
    )

    assert create_export_response.status_code == 201
    export_job = create_export_response.json()
    assert export_job["status"] == ExportJobStatus.QUEUED
    assert export_enqueue_calls == [export_job["id"]]

    monkeypatch.setenv("APP_RUNTIME_DIR", str(runtime_dir))
    with Session(engine) as session:
        completed_job = ExportService(
            TaskRepository(session),
            ExportJobRepository(session),
        ).export_job(export_job["id"])

    assert completed_job.status == ExportJobStatus.COMPLETED
    artifact_path = Path(completed_job.file_path)
    assert artifact_path.exists()
    exported_text = artifact_path.read_text(encoding="utf-8")
    assert "Reviewed launch draft with visible citations and an explicit review gate." in exported_text
    assert str(created_task["id"]) in exported_text

    detail_response = client.get(f"/tasks/{created_task['id']}")

    assert detail_response.status_code == 200
    task_detail = detail_response.json()
    assert task_detail["status"] == TaskStatus.COMPLETED
    assert task_detail["approved_snapshot"]["understanding"]["summary"] == "Approved summary with reviewer edits."
    assert task_detail["approved_snapshot"]["retrieval_hits"][0]["reason"].startswith("Reviewer kept")

