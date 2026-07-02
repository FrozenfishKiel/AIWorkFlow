from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

import app.main as app_main
from app.models import ExportJobStatus, KnowledgeDocumentStatus, TaskStatus
from app.core.settings import get_settings
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.task_repository import TaskRepository
from app.services.export_service import ExportService
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.task_pipeline_service import TaskPipelineService


def test_root_acceptance_covers_index_task_auto_export(
    client,
    engine,
    runtime_dir: Path,
    monkeypatch,
    tmp_path: Path,
) -> None:
    knowledge_source = tmp_path / "brand-guideline.md"
    knowledge_source.write_text(
        "# Brand guideline\n\n"
        "Keep citations visible in exported content.\n\n"
        "Backend records must stay traceable after automatic export.\n\n"
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

    assert processed_task.status == TaskStatus.COMPLETED
    assert processed_task.understanding is not None
    assert processed_task.workflow_result is not None
    assert processed_task.retrieval_hits
    assert processed_task.retrieval_hits[0]["title"] == "Brand guideline"
    assert "citations visible" in processed_task.retrieval_hits[0]["snippet"].lower()
    assert processed_task.approved_snapshot is not None
    assert processed_task.approved_snapshot["workflow_result"]["draft"] == processed_task.workflow_result["draft"]
    assert processed_task.approved_snapshot["retrieval_hits"][0]["title"] == "Brand guideline"

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
    assert processed_task.workflow_result["draft"] in exported_text
    assert str(created_task["id"]) in exported_text

    detail_response = client.get(f"/tasks/{created_task['id']}")

    assert detail_response.status_code == 200
    task_detail = detail_response.json()
    assert task_detail["status"] == TaskStatus.COMPLETED
    assert task_detail["approved_snapshot"]["understanding"]["summary"] == processed_task.understanding["summary"]
    assert task_detail["approved_snapshot"]["retrieval_hits"][0]["title"] == "Brand guideline"

    audit_response = client.get(f"/tasks/{created_task['id']}/audit-logs")

    assert audit_response.status_code == 200
    audit_rows = audit_response.json()
    assert [item["event_type"] for item in audit_rows[:5]] == [
        "export_completed",
        "export_started",
        "export_created",
        "snapshot_persisted",
        "pipeline_completed",
    ]
    assert audit_rows[0]["details"]["export_type"] == "markdown"
    assert audit_rows[0]["details"]["file_path"]


def test_root_acceptance_covers_password_login_file_task_and_artifact_download(
    client,
    engine,
    runtime_dir: Path,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("AUTH_LOGIN_USERNAME", "operator")
    monkeypatch.setenv("AUTH_LOGIN_PASSWORD", "open-sesame")
    monkeypatch.setenv("AUTH_SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()
    app_main.settings = get_settings()

    config_response = client.get("/auth/config")
    assert config_response.status_code == 200
    assert config_response.json()["auth_mode"] == "password_login"

    login_response = client.post(
        "/auth/login",
        json={"username": "operator", "password": "open-sesame"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    me_response = client.get("/auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "operator"

    unauthorized_tasks_response = client.get("/tasks")
    assert unauthorized_tasks_response.status_code == 401

    knowledge_source = tmp_path / "launch-facts.md"
    knowledge_source.write_text(
        "# Launch facts\n\n"
        "All externally visible claims need reviewer-visible citations.\n\n"
        "Final exports must preserve auditability and domain-specific grounding.\n",
        encoding="utf-8",
    )
    upload_source = tmp_path / "launch-brief.md"
    upload_source.write_text(
        "# Launch brief\n\n"
        "Prepare launch copy for the content ops team and keep citations visible.\n",
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
        headers=auth_headers,
        json={
            "title": "Launch facts",
            "source_path": str(knowledge_source),
            "source_type": "launch_facts",
            "domain": "content-ops",
        },
    )
    assert knowledge_response.status_code == 201
    knowledge_document = knowledge_response.json()
    assert knowledge_document["status"] == KnowledgeDocumentStatus.QUEUED
    assert index_enqueue_calls == [knowledge_document["id"]]

    with Session(engine) as session:
        indexed_document = KnowledgeIndexService(KnowledgeRepository(session)).index_document(knowledge_document["id"])
    assert indexed_document.status == KnowledgeDocumentStatus.INDEXED

    upload_response = client.post(
        "/tasks/upload",
        headers=auth_headers,
        data={"knowledge_domain": "content-ops"},
        files={"file": ("launch-brief.md", upload_source.read_bytes(), "text/markdown")},
    )
    assert upload_response.status_code == 201
    created_task = upload_response.json()
    assert created_task["input_type"] == "file"
    assert created_task["knowledge_domain"] == "content-ops"
    assert task_enqueue_calls == [created_task["id"]]

    processed_task = TaskPipelineService(lambda: Session(engine)).run_pipeline(created_task["id"])
    assert processed_task.status == TaskStatus.COMPLETED
    assert processed_task.retrieval_hits
    assert processed_task.retrieval_hits[0]["title"] == "Launch facts"
    assert processed_task.approved_snapshot is not None

    export_response = client.post(
        "/exports",
        headers=auth_headers,
        json={"task_id": created_task["id"], "export_type": "markdown"},
    )
    assert export_response.status_code == 201
    export_job = export_response.json()
    assert export_enqueue_calls == [export_job["id"]]

    monkeypatch.setenv("APP_RUNTIME_DIR", str(runtime_dir))
    with Session(engine) as session:
        completed_job = ExportService(
            TaskRepository(session),
            ExportJobRepository(session),
        ).export_job(export_job["id"])
    assert completed_job.status == ExportJobStatus.COMPLETED

    export_list_response = client.get(
        "/exports",
        headers=auth_headers,
        params={"task_id": created_task["id"]},
    )
    assert export_list_response.status_code == 200
    listed_exports = export_list_response.json()
    assert [job["id"] for job in listed_exports] == [export_job["id"]]

    artifact_response = client.get(
        f"/exports/{export_job['id']}/artifact",
        headers=auth_headers,
    )
    assert artifact_response.status_code == 200
    assert processed_task.workflow_result["draft"] in artifact_response.text

    task_detail_response = client.get(
        f"/tasks/{created_task['id']}",
        headers=auth_headers,
    )
    assert task_detail_response.status_code == 200
    task_detail = task_detail_response.json()
    assert task_detail["approved_snapshot"]["retrieval_hits"][0]["title"] == "Launch facts"

    audit_response = client.get(
        f"/tasks/{created_task['id']}/audit-logs",
        headers=auth_headers,
    )
    assert audit_response.status_code == 200
    audit_rows = audit_response.json()
    assert [item["event_type"] for item in audit_rows[:5]] == [
        "export_completed",
        "export_started",
        "export_created",
        "snapshot_persisted",
        "pipeline_completed",
    ]
    assert audit_rows[0]["details"]["file_path"]
