from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.core.settings import get_settings
from app.models import ExportJob, ExportJobStatus, TaskStatus
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.task_repository import TaskRepository


class ExportService:
    """Creates export jobs and materializes artifacts from approved snapshots.

    Export is intentionally downstream of the review gate. This service never
    reads mutable pre-review fields directly when an approved snapshot exists.
    """

    def __init__(
        self,
        task_repository: TaskRepository,
        export_job_repository: ExportJobRepository,
    ) -> None:
        self.task_repository = task_repository
        self.export_job_repository = export_job_repository
        self.settings = get_settings()

    def create_export_job(self, *, task_id: str | UUID, export_type: str) -> ExportJob:
        """Register an export request for a task that is already approved."""

        task = self.task_repository.require_task(task_id)
        if task.status != TaskStatus.APPROVED or task.approved_snapshot is None:
            raise ValueError("Task must be approved before export.")

        return self.export_job_repository.create_job(task_id=task.id, export_type=export_type)

    def export_job(self, export_job_id: str | UUID) -> ExportJob:
        """Generate the artifact from the canonical approved snapshot.

        A successful export marks the task as completed because the current
        Phase 1 flow treats export as the final terminal step.
        """

        job = self.export_job_repository.require_job(export_job_id)
        task = self.task_repository.require_task(job.task_id)
        approved_snapshot = task.approved_snapshot or {}
        workflow_result = approved_snapshot.get("workflow_result") or {}

        self.export_job_repository.update_job(job=job, status=ExportJobStatus.EXPORTING)
        file_path = self._write_export_file(
            export_job_id=job.id,
            export_type=job.export_type,
            task_id=task.id,
            draft=workflow_result.get("draft", ""),
        )
        self.task_repository.update_status(task=task, status=TaskStatus.COMPLETED)
        return self.export_job_repository.update_job(
            job=job,
            status=ExportJobStatus.COMPLETED,
            file_path=str(file_path),
            error_message=None,
        )

    def resolve_artifact_path(self, export_job_id: str | UUID) -> Path:
        """Return a safe artifact path for a completed export job.

        The download route must not trust the persisted ``file_path`` blindly.
        This guard keeps downloads constrained to the configured exports root
        even if a future bug or manual database edit tampers with that field.
        """

        job = self.export_job_repository.require_job(export_job_id)
        if job.status != ExportJobStatus.COMPLETED or not job.file_path:
            raise ValueError("Export artifact is not ready.")

        candidate = Path(job.file_path).resolve()
        exports_root = self.settings.exports_root.resolve()
        try:
            candidate.relative_to(exports_root)
        except ValueError as exc:
            raise ValueError("Export artifact path is invalid.") from exc

        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError("Export artifact file is missing.")

        return candidate

    def _write_export_file(
        self,
        *,
        export_job_id: UUID,
        export_type: str,
        task_id: UUID,
        draft: str,
    ) -> Path:
        """Write the minimal Phase 1 artifact for the requested export type."""

        suffix = ".md" if export_type == "markdown" else ".txt"
        destination = self.settings.exports_root / f"{export_job_id}{suffix}"
        header = f"# Export for task {task_id}\n\n" if export_type == "markdown" else f"Export for task {task_id}\n\n"
        destination.write_text(f"{header}{draft}".strip() + "\n", encoding="utf-8")
        return destination
