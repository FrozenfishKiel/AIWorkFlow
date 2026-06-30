from __future__ import annotations

import logging

from sqlmodel import Session

from app.core.db import engine
from app.models import ExportJobStatus
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.task_repository import TaskRepository
from app.services.export_service import ExportService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.run_export_job")
def run_export_job(export_job_id: str) -> dict[str, str]:
    """Execute a single export job and persist the generated artifact state."""

    try:
        with Session(engine) as session:
            service = ExportService(TaskRepository(session), ExportJobRepository(session))
            job = service.export_job(export_job_id)
            return {
                "export_job_id": str(job.id),
                "status": job.status,
            }
    except Exception as exc:  # pragma: no cover - worker failure path
        logger.exception("Export job failed for %s", export_job_id)
        with Session(engine) as session:
            repository = ExportJobRepository(session)
            job = repository.get_job(export_job_id)
            if job is not None:
                repository.update_job(
                    job=job,
                    status=ExportJobStatus.FAILED,
                    file_path=None,
                    error_message=str(exc),
                )
        raise
