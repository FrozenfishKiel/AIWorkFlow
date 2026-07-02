from sqlmodel import Session
import importlib

from app.models import ExportJobStatus, TaskStatus
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.task_repository import TaskRepository
from app.services.export_service import ExportService


def _create_auto_completed_task(task_repository: TaskRepository, *, content: str, draft: str):
    task = task_repository.create_task(input_type="text", content=content)
    task_repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "Generated summary",
            "audience": ["brand"],
            "key_points": ["Generated point"],
        },
        retrieval_hits=[],
        workflow_result={
            "draft": draft,
            "review_notes": ["Generated note"],
            "open_questions": [],
        },
    )
    return task_repository.require_task(task.id)


def test_export_service_writes_file_from_auto_stable_snapshot(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Export completed copy.",
        draft="Generated draft ready for export.",
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="markdown")
    completed_job = service.export_job(job.id)

    assert completed_job.status == ExportJobStatus.COMPLETED
    assert completed_job.file_path is not None
    assert "Generated draft ready for export." in open(completed_job.file_path, encoding="utf-8").read()

    refreshed_task = task_repository.require_task(task.id)
    assert refreshed_task.status == TaskStatus.COMPLETED


def test_export_service_marks_task_exporting_before_writing_artifact(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Export completed copy.",
        draft="Generated draft ready for export.",
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="markdown")

    def fake_write_export_file(**kwargs):
        exporting_task = task_repository.require_task(task.id)
        assert exporting_task.status == TaskStatus.EXPORTING
        return service.settings.exports_root / f"{kwargs['export_job_id']}.md"

    service._write_export_file = fake_write_export_file  # type: ignore[method-assign]

    completed_job = service.export_job(job.id)

    assert completed_job.status == ExportJobStatus.COMPLETED
    assert task_repository.require_task(task.id).status == TaskStatus.COMPLETED


def test_export_service_restores_task_to_completed_when_artifact_write_fails(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Export completed copy.",
        draft="Generated draft ready for export.",
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="markdown")

    def fake_write_export_file(**kwargs):
        raise RuntimeError("disk full")

    service._write_export_file = fake_write_export_file  # type: ignore[method-assign]

    try:
        service.export_job(job.id)
    except RuntimeError as exc:
        assert str(exc) == "disk full"
    else:  # pragma: no cover - the test is specifically for the failure path
        raise AssertionError("Expected export_job to raise when artifact writing fails.")

    assert task_repository.require_task(task.id).status == TaskStatus.COMPLETED


def test_export_service_allows_follow_up_export_for_completed_task(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Export completed copy again.",
        draft="Generated draft ready for export again.",
    )

    service = ExportService(task_repository, export_repository)

    job = service.create_export_job(task_id=task.id, export_type="structured_text")

    assert job.export_type == "structured_text"
    assert job.task_id == task.id


def test_export_service_restores_completed_status_when_follow_up_export_fails(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Retry completed export safely.",
        draft="Generated draft ready for export retry.",
    )

    service = ExportService(task_repository, export_repository)
    job = export_repository.create_job(task_id=task.id, export_type="structured_text")

    def fake_write_export_file(**kwargs):
        raise RuntimeError("disk full")

    service._write_export_file = fake_write_export_file  # type: ignore[method-assign]

    try:
        service.export_job(job.id)
    except RuntimeError as exc:
        assert str(exc) == "disk full"
    else:  # pragma: no cover - the test is specifically for the failure path
        raise AssertionError("Expected export_job to raise when artifact writing fails.")

    assert task_repository.require_task(task.id).status == TaskStatus.COMPLETED


def test_export_service_persists_export_audit_events(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Audit export chain.",
        draft="Generated draft ready for auditable export.",
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="markdown")
    service.export_job(job.id)

    audit_module = importlib.import_module("app.models.audit_log")
    AuditLog = audit_module.AuditLog
    audit_rows = list(
        session.exec(
            AuditLog.__table__.select().where(AuditLog.task_id == task.id).order_by(AuditLog.created_at.asc())
        )
    )

    export_events = [(row.event_type, row.outcome) for row in audit_rows if row.export_job_id == job.id]
    assert export_events == [
        ("export_created", "success"),
        ("export_started", "success"),
        ("export_completed", "success"),
    ]
    assert audit_rows[-1].details["export_type"] == "markdown"
    assert audit_rows[-1].details["file_path"]


def test_export_service_persists_failed_export_audit_event(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Audit failed export chain.",
        draft="Generated draft that will fail to write.",
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="structured_text")

    def fake_write_export_file(**kwargs):
        raise RuntimeError("disk full")

    service._write_export_file = fake_write_export_file  # type: ignore[method-assign]

    try:
        service.export_job(job.id)
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected export_job to raise when artifact writing fails.")

    audit_module = importlib.import_module("app.models.audit_log")
    AuditLog = audit_module.AuditLog
    audit_rows = list(
        session.exec(
            AuditLog.__table__.select().where(AuditLog.task_id == task.id).order_by(AuditLog.created_at.asc())
        )
    )

    assert [(row.event_type, row.outcome) for row in audit_rows if row.export_job_id == job.id] == [
        ("export_created", "success"),
        ("export_started", "success"),
        ("export_failed", "failure"),
    ]
    assert audit_rows[-1].details["error_message"] == "disk full"


def test_export_service_returns_completed_job_with_loaded_fields_after_session_close(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = _create_auto_completed_task(
        task_repository,
        content="Detached job regression.",
        draft="Generated draft for detached export job regression.",
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="markdown")

    completed_job = service.export_job(job.id)
    session.close()

    assert completed_job.status == ExportJobStatus.COMPLETED
    assert completed_job.file_path is not None


def test_export_service_writes_product_content_bundle_when_task_uses_new_generation_shape(session: Session) -> None:
    task_repository = TaskRepository(session)
    export_repository = ExportJobRepository(session)
    task = task_repository.create_task(
        input_type="product_request",
        content='{"product":{"name":"清透防晒霜"},"task_description":"生成三类初稿"}',
    )
    task_repository.update_pipeline_results(
        task=task,
        status=TaskStatus.COMPLETED,
        understanding={
            "summary": "清透防晒霜适合夏季通勤场景。",
            "target_audience": "通勤女生",
            "use_scenarios": ["夏季通勤"],
            "primary_value_points": ["清爽不搓泥", "补涂方便"],
        },
        retrieval_hits=[],
        workflow_result={
            "selling_points_copy": ["清爽不搓泥，补涂更轻松。"],
            "detail_page_copy": "详情页重点突出轻透肤感和高倍防护。",
            "social_seed_copy": "通勤补涂不搓泥，这支我会一直放包里。",
            "risk_notes": ["避免使用绝对化防晒承诺。"],
            "applied_guidelines": ["品牌语气规范"],
        },
    )

    service = ExportService(task_repository, export_repository)
    job = service.create_export_job(task_id=task.id, export_type="markdown")
    completed_job = service.export_job(job.id)

    contents = open(completed_job.file_path, encoding="utf-8").read()
    assert "清爽不搓泥，补涂更轻松。" in contents
    assert "详情页重点突出轻透肤感和高倍防护。" in contents
    assert "通勤补涂不搓泥，这支我会一直放包里。" in contents
