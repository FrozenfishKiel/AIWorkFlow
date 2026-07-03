from unittest.mock import MagicMock
from pathlib import Path

import pytest
from sqlmodel import Session

from app.models.task import TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.task_pipeline_service import TaskPipelineService


def test_create_task_returns_queued_task_and_lists_it(
    client,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_tasks.run_task_pipeline.delay", enqueue_mock)

    create_response = client.post(
        "/tasks",
        json={
            "input_type": "text",
            "content": "Summarize this market article for content ops.",
            "knowledge_domain": "content-ops",
        },
    )

    assert create_response.status_code == 201
    created_task = create_response.json()
    assert created_task["status"] == TaskStatus.QUEUED
    assert created_task["input_type"] == "text"
    assert created_task["content"] == "Summarize this market article for content ops."
    assert created_task["knowledge_domain"] == "content-ops"
    enqueue_mock.assert_called_once_with(created_task["id"])

    list_response = client.get("/tasks")

    assert list_response.status_code == 200
    listed_tasks = list_response.json()
    assert len(listed_tasks) == 1
    assert listed_tasks[0]["id"] == created_task["id"]
    assert listed_tasks[0]["status"] == TaskStatus.QUEUED


@pytest.mark.parametrize("origin", ["http://127.0.0.1:4173", "http://127.0.0.1:5175"])
def test_tasks_route_accepts_local_dev_cors_preflight_on_dynamic_vite_port(
    client,
    origin: str,
) -> None:
    response = client.options(
        "/tasks",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_create_task_rejects_file_input_for_json_endpoint(client) -> None:
    response = client.post(
        "/tasks",
        json={"input_type": "file", "content": "D:\\unsafe-path.txt"},
    )

    assert response.status_code == 422


def test_create_task_returns_503_and_cleans_up_when_enqueue_fails(
    client,
    monkeypatch,
) -> None:
    def raise_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr("app.api.routes_tasks.run_task_pipeline.delay", raise_enqueue)

    create_response = client.post(
        "/tasks",
        json={"input_type": "text", "content": "Queue this task safely."},
    )

    assert create_response.status_code == 503
    assert create_response.json()["detail"] == "Task queue is temporarily unavailable."

    list_response = client.get("/tasks")
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_get_task_detail_returns_pipeline_payload(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="url", content="https://example.com/article")
    task.review = {
        "decision": "approved",
        "reviewer_note": "Legacy internal note should stay out of the public payload.",
    }
    session.add(task)
    session.commit()
    session.refresh(task)
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "The article focuses on launch messaging and review constraints.",
            "audience": ["brand", "content-ops"],
            "key_points": ["Keep claims reviewable."],
            "risk_points": ["Claims still require reviewer verification before export."],
            "uncertain_items": ["Final business angle still needs human confirmation."],
            "input_quality": {
                "source_kind": "url",
                "quality_flags": [],
                "extracted_length": 128,
            },
        },
        retrieval_hits=[
            {
                "source_id": "kb-brand-guideline",
                "title": "Brand tone guideline",
                "snippet": "Keep the tone practical and avoid over-promising.",
                "reason": "Adds a visible tone constraint to the generated draft.",
            }
        ],
        workflow_result={
            "draft": "This is a draft workflow result waiting for human review.",
            "review_notes": ["Manual approval is required before export."],
            "open_questions": ["Does the tone align with the campaign goal?"],
            "evidence_used": [
                {
                    "source_id": "kb-brand-guideline",
                    "title": "Brand tone guideline",
                    "snippet": "Keep the tone practical and avoid over-promising.",
                    "reason": "Adds a visible tone constraint to the generated draft.",
                }
            ],
            "uncertainties": ["Final business angle still needs human confirmation."],
            "manual_checks": ["Verify every externally visible claim against the cited evidence."],
            "context_summary": {
                "selected_hit_count": 1,
                "context_sections": ["task_goal", "input_summary", "retrieval_evidence"],
            },
            "processing_trace": [
                "Parsed url input into reviewer-usable plain text.",
                "Assembled a constrained context package before generation.",
            ],
        },
    )

    detail_response = client.get(f"/tasks/{task.id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == str(task.id)
    assert detail["status"] == TaskStatus.COMPLETED
    assert (
        detail["understanding"]["summary"]
        == "The article focuses on launch messaging and review constraints."
    )
    assert detail["understanding"]["input_quality"]["source_kind"] == "url"
    assert detail["retrieval_hits"][0]["source_id"] == "kb-brand-guideline"
    assert (
        detail["workflow_result"]["draft"]
        == "This is a draft workflow result waiting for human review."
    )
    assert detail["workflow_result"]["evidence_used"][0]["source_id"] == "kb-brand-guideline"
    assert detail["workflow_result"]["evidence_used"][0]["snippet"] == "Keep the tone practical and avoid over-promising."
    assert detail["workflow_result"]["evidence_used"][0]["reason"] == "Adds a visible tone constraint to the generated draft."
    assert detail["workflow_result"]["processing_trace"]
    assert detail["approved_snapshot"]["workflow_result"]["draft"] == "This is a draft workflow result waiting for human review."
    assert "review" not in detail


def test_review_routes_are_not_exposed_anymore(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Legacy review routes should stay retired.")

    responses = [
        client.post(f"/reviews/{task.id}/start"),
        client.put(f"/reviews/{task.id}", json={}),
        client.post(f"/reviews/{task.id}/approve", json={}),
        client.post(f"/reviews/{task.id}/reject", json={}),
        client.post(f"/reviews/{task.id}/rerun", json={}),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404, 404]


def test_task_audit_log_endpoint_returns_latest_first_timeline(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Need an auditable task timeline.")
    TaskPipelineService(lambda: Session(session.get_bind())).run_pipeline(task.id)

    export_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "markdown"},
    )
    assert export_response.status_code == 201

    response = client.get(f"/tasks/{task.id}/audit-logs")

    assert response.status_code == 200
    payload = response.json()
    assert [item["event_type"] for item in payload] == [
        "export_completed",
        "export_started",
        "export_created",
        "snapshot_persisted",
        "pipeline_completed",
    ]
    assert payload[0]["task_id"] == str(task.id)
    assert payload[0]["summary"]
    assert payload[0]["details"]["export_type"] == "markdown"


def test_export_create_and_detail_return_reviewed_output_artifact(
    client,
    session: Session,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", enqueue_mock)

    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Export this reviewed content.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated draft that is already export ready.",
            "review_notes": ["Generated note"],
            "open_questions": ["Generated question"],
        },
    )

    create_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "markdown"},
    )

    assert create_response.status_code == 201
    export_job = create_response.json()
    assert export_job["status"] == "queued"
    assert export_job["export_type"] == "markdown"
    enqueue_mock.assert_called_once_with(export_job["id"])

    detail_response = client.get(f"/exports/{export_job['id']}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["task_id"] == str(task.id)
    assert detail["status"] == "queued"


def test_export_requires_approved_task(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Still waiting for review.")

    create_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "markdown"},
    )

    assert create_response.status_code == 409
    assert create_response.json()["detail"] == "Task must have a stable snapshot before export."


def test_export_artifact_download_returns_completed_file_contents(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Download this reviewed export.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated export-ready draft.",
            "review_notes": ["Generated note"],
            "open_questions": ["Generated question"],
        },
    )

    create_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "markdown"},
    )
    export_job = create_response.json()

    from app.repositories.export_job_repository import ExportJobRepository
    from app.services.export_service import ExportService

    session.expire_all()
    export_service = ExportService(repository, ExportJobRepository(session))
    completed_job = export_service.export_job(export_job["id"])

    download_response = client.get(f"/exports/{completed_job.id}/artifact")

    assert download_response.status_code == 200
    assert "Generated export-ready draft." in download_response.text
    assert download_response.headers["content-type"].startswith("text/markdown")


def test_export_job_runs_inline_when_queue_is_unavailable(
    client,
    session: Session,
    monkeypatch,
) -> None:
    def raise_enqueue(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", raise_enqueue)

    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Export inline when the queue is down.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated export-ready draft.",
            "review_notes": ["Generated note"],
            "open_questions": ["Generated question"],
        },
    )

    create_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "markdown"},
    )

    assert create_response.status_code == 201
    export_job = create_response.json()
    assert export_job["status"] == "completed"
    assert export_job["file_path"]

    download_response = client.get(f"/exports/{export_job['id']}/artifact")

    assert download_response.status_code == 200
    assert "Generated export-ready draft." in download_response.text


def test_export_artifact_download_requires_completed_job(
    client,
    session: Session,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", enqueue_mock)

    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Export still queued.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated draft.",
            "review_notes": [],
            "open_questions": [],
        },
    )

    create_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "markdown"},
    )

    assert create_response.status_code == 201
    export_job = create_response.json()

    download_response = client.get(f"/exports/{export_job['id']}/artifact")

    assert download_response.status_code == 409
    assert download_response.json()["detail"] == "Export artifact is not ready."


def test_completed_task_can_create_follow_up_export_job(
    client,
    session: Session,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", enqueue_mock)

    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Export this task twice.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated draft.",
            "review_notes": [],
            "open_questions": [],
        },
    )

    first_create_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "markdown"},
    )
    assert first_create_response.status_code == 201

    from app.repositories.export_job_repository import ExportJobRepository
    from app.services.export_service import ExportService

    export_service = ExportService(repository, ExportJobRepository(session))
    export_service.export_job(first_create_response.json()["id"])

    second_create_response = client.post(
        "/exports",
        json={"task_id": str(task.id), "export_type": "structured_text"},
    )

    assert second_create_response.status_code == 201
    assert second_create_response.json()["export_type"] == "structured_text"


def test_export_job_list_returns_latest_first_and_can_filter_by_task(
    client,
    session: Session,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_exports.run_export_job.delay", enqueue_mock)

    repository = TaskRepository(session)

    task_one = repository.create_task(input_type="text", content="First export task.")
    task_two = repository.create_task(input_type="text", content="Second export task.")

    for task in (task_one, task_two):
        repository.update_pipeline_results(
            task=task,
            status=TaskStatus.COMPLETED,
            understanding={
                "summary": "Generated summary",
                "audience": ["brand"],
                "key_points": ["Generated point"],
            },
            retrieval_hits=[],
            workflow_result={
                "draft": "Generated draft.",
                "review_notes": [],
                "open_questions": [],
            },
        )

    first_job = client.post(
        "/exports",
        json={"task_id": str(task_one.id), "export_type": "markdown"},
    ).json()
    second_job = client.post(
        "/exports",
        json={"task_id": str(task_two.id), "export_type": "structured_text"},
    ).json()

    list_response = client.get("/exports")

    assert list_response.status_code == 200
    jobs = list_response.json()
    assert [job["id"] for job in jobs[:2]] == [second_job["id"], first_job["id"]]

    filtered_response = client.get("/exports", params={"task_id": str(task_one.id)})

    assert filtered_response.status_code == 200
    filtered_jobs = filtered_response.json()
    assert len(filtered_jobs) == 1
    assert filtered_jobs[0]["id"] == first_job["id"]
    assert filtered_jobs[0]["task_id"] == str(task_one.id)


def test_create_file_task_accepts_multipart_upload_and_enqueues_processing(
    client,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_tasks.run_task_pipeline.delay", enqueue_mock)

    response = client.post(
        "/tasks/upload",
        data={"knowledge_domain": "brand"},
        files={"file": ("launch-brief.md", b"# Brief\n\nHuman review stays mandatory.\n", "text/markdown")},
    )

    assert response.status_code == 201
    created_task = response.json()
    assert created_task["status"] == TaskStatus.QUEUED
    assert created_task["input_type"] == "file"
    assert created_task["knowledge_domain"] == "brand"
    assert Path(created_task["content"]).suffix == ".md"
    assert Path(created_task["content"]).name.startswith("launch-brief")
    enqueue_mock.assert_called_once_with(created_task["id"])


def test_knowledge_index_local_registers_document_and_enqueues_index_job(
    client,
    monkeypatch,
    tmp_path,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_knowledge.index_knowledge_document.delay", enqueue_mock)

    source_file = tmp_path / "faq.md"
    source_file.write_text(
        "# FAQ\n\n"
        "Always keep citations visible for reviewers.\n",
        encoding="utf-8",
    )

    response = client.post(
        "/knowledge/index-local",
        json={
            "title": "FAQ",
            "source_path": str(source_file),
            "source_type": "faq",
            "domain": "support",
        },
    )

    assert response.status_code == 201
    document = response.json()
    assert document["title"] == "FAQ"
    assert document["status"] == "queued"
    enqueue_mock.assert_called_once_with(document["id"])


def test_knowledge_document_list_returns_registered_documents_in_latest_first_order(
    client,
    session: Session,
    tmp_path,
) -> None:
    from app.repositories.knowledge_repository import KnowledgeRepository

    repository = KnowledgeRepository(session)

    older_file = tmp_path / "older.md"
    older_file.write_text("# Older\n\nOlder guidance.\n", encoding="utf-8")
    newer_file = tmp_path / "newer.md"
    newer_file.write_text("# Newer\n\nNewer guidance.\n", encoding="utf-8")

    repository.create_document(
        title="Older Guide",
        source_path=str(older_file),
        source_type="guide",
        domain="brand",
    )
    repository.create_document(
        title="Newer Guide",
        source_path=str(newer_file),
        source_type="faq",
        domain="content-ops",
    )

    response = client.get("/knowledge/documents")

    assert response.status_code == 200
    documents = response.json()
    assert [item["title"] for item in documents] == ["Newer Guide", "Older Guide"]
    assert documents[0]["source_type"] == "faq"
    assert documents[1]["domain"] == "brand"


def test_knowledge_document_detail_returns_chunk_preview_for_indexed_document(
    client,
    session: Session,
    tmp_path,
) -> None:
    from app.models import KnowledgeDocumentStatus
    from app.repositories.knowledge_repository import KnowledgeRepository

    repository = KnowledgeRepository(session)

    source_file = tmp_path / "playbook.md"
    source_file.write_text("# Playbook\n\nKeep reviewer-visible evidence attached.\n", encoding="utf-8")

    document = repository.create_document(
        title="Launch Playbook",
        source_path=str(source_file),
        source_type="guide",
        domain="brand",
    )
    repository.replace_chunks(
        document=document,
        contents=[
            "Keep reviewer-visible evidence attached to every generated recommendation.",
            "Flag uncertain claims before approval so the final export does not hide risk.",
        ],
    )
    repository.set_document_status(
        document=document,
        status=KnowledgeDocumentStatus.INDEXED,
        chunk_count=2,
    )

    response = client.get(f"/knowledge/documents/{document.id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["title"] == "Launch Playbook"
    assert detail["status"] == "indexed"
    assert detail["chunk_count"] == 2
    assert detail["chunk_preview"] == [
        {
            "chunk_index": 0,
            "content_preview": "Keep reviewer-visible evidence attached to every generated recommendation.",
        },
        {
            "chunk_index": 1,
            "content_preview": "Flag uncertain claims before approval so the final export does not hide risk.",
        },
    ]


def test_auth_gate_requires_bearer_token_when_configured(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("API_ACCESS_TOKEN", "secret-token")

    from app.core.settings import get_settings
    import app.main as app_main

    get_settings.cache_clear()
    app_main.settings = get_settings()

    unauthorized_response = client.get("/tasks")
    assert unauthorized_response.status_code == 401
    assert unauthorized_response.json()["detail"] == "Missing or invalid bearer token."

    wrong_token_response = client.get(
        "/tasks",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert wrong_token_response.status_code == 401
    assert wrong_token_response.json()["detail"] == "Missing or invalid bearer token."

    authorized_response = client.get(
        "/tasks",
        headers={"Authorization": "Bearer secret-token"},
    )
    assert authorized_response.status_code == 200

    health_response = client.get("/health")
    assert health_response.status_code == 200

    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    get_settings.cache_clear()
    app_main.settings = get_settings()


def test_password_login_issues_signed_token_and_protects_routes(
    client,
    monkeypatch,
) -> None:
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("AUTH_LOGIN_USERNAME", "operator")
    monkeypatch.setenv("AUTH_LOGIN_PASSWORD", "open-sesame")
    monkeypatch.setenv("AUTH_SECRET_KEY", "0123456789abcdef0123456789abcdef")

    from app.core.settings import get_settings
    import app.main as app_main

    get_settings.cache_clear()
    app_main.settings = get_settings()

    config_response = client.get("/auth/config")

    assert config_response.status_code == 200
    assert config_response.json()["auth_mode"] == "password_login"

    unauthorized_response = client.get("/tasks")
    assert unauthorized_response.status_code == 401
    assert unauthorized_response.json()["detail"] == "Missing or invalid access token."

    bad_login_response = client.post(
        "/auth/login",
        json={"username": "operator", "password": "wrong-password"},
    )
    assert bad_login_response.status_code == 401
    assert bad_login_response.json()["detail"] == "Invalid username or password."

    login_response = client.post(
        "/auth/login",
        json={"username": "operator", "password": "open-sesame"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["token_type"] == "bearer"
    assert login_payload["username"] == "operator"
    assert login_payload["access_token"]

    auth_headers = {"Authorization": f"Bearer {login_payload['access_token']}"}

    me_response = client.get("/auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "operator"
    assert me_response.json()["auth_mode"] == "password_login"

    tasks_response = client.get("/tasks", headers=auth_headers)
    assert tasks_response.status_code == 200

    for env_name in ("AUTH_LOGIN_USERNAME", "AUTH_LOGIN_PASSWORD", "AUTH_SECRET_KEY"):
        monkeypatch.delenv(env_name, raising=False)
    get_settings.cache_clear()
    app_main.settings = get_settings()
