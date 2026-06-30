from sqlmodel import Session

from app.models import ExportJobStatus, TaskStatus
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.task_repository import TaskRepository
from app.services.export_service import ExportService


def test_export_service_writes_file_from_approved_snapshot(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = task_repository.create_task(input_type="text", content="Export approved copy.")
    task_repository.update_pipeline_results(
        task=task,
        status=TaskStatus.REVIEW_PENDING,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": "Generated draft",
            "review_notes": ["Generated note"],
            "open_questions": [],
        },
    )
    task_repository.save_review(
        task=task,
        status=TaskStatus.APPROVED,
        review={
            "decision": "approved",
            "reviewer_note": "Approved.",
            "rejection_reason": None,
            "not_adopted_items": [],
            "edited_understanding": None,
            "edited_retrieval_hits": [],
            "edited_workflow_result": {
                "draft": "Approved draft for export",
                "review_notes": ["Approved note"],
                "open_questions": [],
            },
        },
        approved_snapshot={
            "understanding": task.understanding,
            "retrieval_hits": task.retrieval_hits,
            "workflow_result": {
                "draft": "Approved draft for export",
                "review_notes": ["Approved note"],
                "open_questions": [],
            },
        },
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="markdown")
    completed_job = service.export_job(job.id)

    assert completed_job.status == ExportJobStatus.COMPLETED
    assert completed_job.file_path is not None
    assert "Approved draft for export" in open(completed_job.file_path, encoding="utf-8").read()

    refreshed_task = task_repository.require_task(task.id)
    assert refreshed_task.status == TaskStatus.COMPLETED
