from unittest.mock import MagicMock
from pathlib import Path

from sqlmodel import Session

from app.models.task import TaskStatus
from app.repositories.task_repository import TaskRepository


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
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.REVIEW_PENDING,
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
    assert detail["status"] == TaskStatus.REVIEW_PENDING
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
    assert detail["workflow_result"]["processing_trace"]


def test_review_start_save_and_approve_persists_reviewer_changes(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Review this generated launch draft.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.REVIEW_PENDING,
        understanding={
            "summary": "Original summary",
            "audience": ["brand"],
            "key_points": ["Original point"],
        },
        retrieval_hits=[
            {
                "source_id": "kb-original",
                "title": "Original source",
                "snippet": "Original support",
                "reason": "Original reason",
            }
        ],
        workflow_result={
            "draft": "Original workflow draft",
            "review_notes": ["Original note"],
            "open_questions": ["Original question"],
        },
    )

    start_response = client.post(f"/reviews/{task.id}/start")

    assert start_response.status_code == 200
    started_task = start_response.json()
    assert started_task["status"] == TaskStatus.REVIEWING

    review_payload = {
        "edited_understanding": {
            "summary": "Edited summary for approval.",
            "audience": ["brand", "ops"],
            "key_points": ["Edited point 1", "Edited point 2"],
            "risk_points": ["Claims still require reviewer verification before export."],
            "uncertain_items": ["Final business angle still needs human confirmation."],
            "input_quality": {
                "source_kind": "text",
                "quality_flags": [],
                "extracted_length": 64,
            },
        },
        "edited_retrieval_hits": [
            {
                "source_id": "kb-replaced",
                "title": "Replacement source",
                "snippet": "Replacement support",
                "reason": "Reviewer replaced the citation.",
            }
        ],
        "edited_workflow_result": {
            "draft": "Edited workflow draft ready for export.",
            "review_notes": ["Keep the promise grounded."],
            "open_questions": ["Is legal review needed?"],
        },
        "not_adopted_items": ["Dropped the unsupported growth claim."],
        "reviewer_note": "Edited source and copy before approval.",
    }

    save_response = client.put(f"/reviews/{task.id}", json=review_payload)

    assert save_response.status_code == 200
    saved_task = save_response.json()
    assert saved_task["status"] == TaskStatus.REVIEWING
    assert saved_task["review"]["decision"] == "in_review"
    assert saved_task["review"]["edited_workflow_result"]["draft"] == "Edited workflow draft ready for export."
    assert saved_task["review"]["not_adopted_items"] == ["Dropped the unsupported growth claim."]

    approve_response = client.post(f"/reviews/{task.id}/approve", json=review_payload)

    assert approve_response.status_code == 200
    approved_task = approve_response.json()
    assert approved_task["status"] == TaskStatus.APPROVED
    assert approved_task["review"]["decision"] == "approved"
    assert approved_task["review"]["edited_understanding"]["summary"] == "Edited summary for approval."
    assert approved_task["review"]["edited_understanding"]["risk_points"] == [
        "Claims still require reviewer verification before export."
    ]
    assert approved_task["approved_snapshot"]["workflow_result"]["draft"] == "Edited workflow draft ready for export."
    assert approved_task["approved_snapshot"]["understanding"]["summary"] == "Edited summary for approval."

    detail_response = client.get(f"/tasks/{task.id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == TaskStatus.APPROVED
    assert detail["review"]["edited_retrieval_hits"][0]["source_id"] == "kb-replaced"
    assert detail["approved_snapshot"]["retrieval_hits"][0]["source_id"] == "kb-replaced"


def test_review_reject_marks_task_rejected_with_reason(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Reject this workflow result.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.REVIEW_PENDING,
        understanding={
            "summary": "Needs changes",
            "audience": ["brand"],
            "key_points": ["Claim cannot be verified"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "This claim is too strong.",
            "review_notes": ["Claims need proof."],
            "open_questions": ["Can we verify the metric?"],
        },
    )
    client.post(f"/reviews/{task.id}/start")

    reject_response = client.post(
        f"/reviews/{task.id}/reject",
        json={"rejection_reason": "The core claim is unsupported and must be regenerated."},
    )

    assert reject_response.status_code == 200
    rejected_task = reject_response.json()
    assert rejected_task["status"] == TaskStatus.REJECTED
    assert rejected_task["review"]["decision"] == "rejected"
    assert rejected_task["review"]["rejection_reason"] == "The core claim is unsupported and must be regenerated."


def test_review_rerun_requeues_rejected_task_with_reason(
    client,
    session: Session,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_reviews.run_task_pipeline.delay", enqueue_mock)

    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Retry this workflow result.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.REVIEW_PENDING,
        understanding={
            "summary": "Needs rework",
            "audience": ["brand"],
            "key_points": ["Unsupported claim"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Needs a safer angle.",
            "review_notes": ["Claims need proof."],
            "open_questions": ["Can we reframe the promise?"],
        },
    )
    client.post(f"/reviews/{task.id}/start")
    client.post(
        f"/reviews/{task.id}/reject",
        json={"rejection_reason": "Unsupported claim."},
    )

    rerun_response = client.post(
        f"/reviews/{task.id}/rerun",
        json={"rerun_reason": "Regenerate with a safer brand angle."},
    )

    assert rerun_response.status_code == 200
    rerun_task = rerun_response.json()
    assert rerun_task["status"] == TaskStatus.QUEUED
    assert rerun_task["review"]["rerun_reason"] == "Regenerate with a safer brand angle."
    enqueue_mock.assert_called_once_with(str(task.id))


def test_review_routes_reject_invalid_state_transitions(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="This task is still queued.")

    start_response = client.post(f"/reviews/{task.id}/start")

    assert start_response.status_code == 409
    assert start_response.json()["detail"] == "Task is not ready for review."

    approve_response = client.post(
        f"/reviews/{task.id}/approve",
        json={
            "edited_understanding": None,
            "edited_retrieval_hits": None,
            "edited_workflow_result": None,
            "not_adopted_items": [],
            "reviewer_note": "Cannot approve directly.",
        },
    )

    assert approve_response.status_code == 409
    assert approve_response.json()["detail"] == "Task must be in reviewing before this action."


def test_review_rerun_does_not_enqueue_when_task_is_not_rejected(
    client,
    session: Session,
    monkeypatch,
) -> None:
    enqueue_mock = MagicMock()
    monkeypatch.setattr("app.api.routes_reviews.run_task_pipeline.delay", enqueue_mock)

    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="This task never reached rejected state.")

    rerun_response = client.post(
        f"/reviews/{task.id}/rerun",
        json={"rerun_reason": "This should not queue."},
    )

    assert rerun_response.status_code == 409
    assert rerun_response.json()["detail"] == "Task must be rejected before rerun."
    enqueue_mock.assert_not_called()


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
        status=TaskStatus.REVIEW_PENDING,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated draft that should not be exported directly.",
            "review_notes": ["Generated note"],
            "open_questions": ["Generated question"],
        },
    )
    client.post(f"/reviews/{task.id}/start")
    client.post(f"/reviews/{task.id}/approve", json={
        "edited_understanding": None,
        "edited_retrieval_hits": [],
        "edited_workflow_result": {
            "draft": "Reviewed export-ready draft.",
            "review_notes": ["Approved note"],
            "open_questions": [],
        },
        "not_adopted_items": [],
        "reviewer_note": "Approved for export.",
    })

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
    assert create_response.json()["detail"] == "Task must be approved before export."


def test_export_artifact_download_returns_completed_file_contents(
    client,
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(input_type="text", content="Download this reviewed export.")
    repository.update_pipeline_results(
        task=task,
        status=TaskStatus.REVIEW_PENDING,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated draft that should not be exported directly.",
            "review_notes": ["Generated note"],
            "open_questions": ["Generated question"],
        },
    )
    client.post(f"/reviews/{task.id}/start")
    client.post(
        f"/reviews/{task.id}/approve",
        json={
            "edited_understanding": None,
            "edited_retrieval_hits": [],
            "edited_workflow_result": {
                "draft": "Reviewed export-ready draft.",
                "review_notes": ["Approved note"],
                "open_questions": [],
            },
            "not_adopted_items": [],
            "reviewer_note": "Approved for export.",
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
    assert "Reviewed export-ready draft." in download_response.text
    assert download_response.headers["content-type"].startswith("text/markdown")


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
        status=TaskStatus.REVIEW_PENDING,
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
    client.post(f"/reviews/{task.id}/start")
    client.post(
        f"/reviews/{task.id}/approve",
        json={
            "edited_understanding": None,
            "edited_retrieval_hits": [],
            "edited_workflow_result": None,
            "not_adopted_items": [],
            "reviewer_note": "Approved for export.",
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
