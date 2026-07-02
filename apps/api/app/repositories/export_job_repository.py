from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.models import ExportJob, ExportJobStatus


class ExportJobRepository:
    """Persistence helpers for export job records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(self, *, task_id: UUID, export_type: str) -> ExportJob:
        job = ExportJob(task_id=task_id, export_type=export_type)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_job(self, export_job_id: str | UUID) -> ExportJob | None:
        return self.session.get(ExportJob, UUID(str(export_job_id)))

    def require_job(self, export_job_id: str | UUID) -> ExportJob:
        job = self.get_job(export_job_id)
        if job is None:
            raise LookupError(f"Export job not found: {export_job_id}")
        return job

    def list_jobs(self, *, task_id: str | UUID | None = None) -> list[ExportJob]:
        statement = select(ExportJob).order_by(ExportJob.created_at.desc())
        if task_id is not None:
            statement = statement.where(ExportJob.task_id == UUID(str(task_id)))
        return list(self.session.exec(statement))

    def update_job(
        self,
        *,
        job: ExportJob,
        status: ExportJobStatus,
        file_path: str | None = None,
        error_message: str | None = None,
    ) -> ExportJob:
        job.status = status
        job.file_path = file_path
        job.error_message = error_message
        job.updated_at = datetime.now(timezone.utc)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job
