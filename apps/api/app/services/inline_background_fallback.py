from __future__ import annotations

from sqlmodel import Session

from app.core.settings import get_settings
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.task_repository import TaskRepository
from app.services.export_service import ExportService
from app.services.task_pipeline_service import TaskPipelineService


def should_use_inline_background_fallback() -> bool:
    """Allow local runs to stay usable when Redis/Celery is not available."""

    return get_settings().allow_inline_background_fallback


def run_task_pipeline_inline(session: Session, task_id: str) -> None:
    """Execute the task pipeline against the current request database bind."""

    bind = session.get_bind()
    TaskPipelineService(lambda: Session(bind)).run_pipeline(task_id)


def run_export_job_inline(session: Session, export_job_id: str) -> None:
    """Materialize an export artifact in-process against the current request session."""

    ExportService(
        TaskRepository(session),
        ExportJobRepository(session),
        AuditLogRepository(session),
    ).export_job(export_job_id)
