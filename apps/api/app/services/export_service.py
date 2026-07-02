from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.core.settings import get_settings
from app.models import AuditEventType, AuditOutcome, ExportJob, ExportJobStatus, TaskStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.task_repository import TaskRepository


class ExportService:
    """Creates export jobs and materializes artifacts from stable task snapshots.

    The persisted snapshot still lives under the legacy ``approved_snapshot``
    field name for now, but it is no longer owned exclusively by human review.
    """

    def __init__(
        self,
        task_repository: TaskRepository,
        export_job_repository: ExportJobRepository,
        audit_log_repository: AuditLogRepository | None = None,
    ) -> None:
        self.task_repository = task_repository
        self.export_job_repository = export_job_repository
        self.audit_log_repository = audit_log_repository or AuditLogRepository(task_repository.session)
        self.settings = get_settings()

    def create_export_job(self, *, task_id: str | UUID, export_type: str) -> ExportJob:
        """Register an export request for a task with a stable snapshot."""

        task = self.task_repository.require_task(task_id)
        if task.approved_snapshot is None or task.status != TaskStatus.COMPLETED:
            raise ValueError("Task must have a stable snapshot before export.")

        job = self.export_job_repository.create_job(task_id=task.id, export_type=export_type)
        self.audit_log_repository.create_log(
            task_id=task.id,
            export_job_id=job.id,
            event_type=AuditEventType.EXPORT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            summary=f"{export_type} export job created.",
            details={"export_type": export_type},
        )
        return job

    def export_job(self, export_job_id: str | UUID) -> ExportJob:
        """Generate the artifact from the canonical stable snapshot.

        A successful export marks the task as completed because the current
        Phase 1 flow treats export as the final terminal step.
        """

        job = self.export_job_repository.require_job(export_job_id)
        task = self.task_repository.require_task(job.task_id)
        approved_snapshot = task.approved_snapshot or {}
        workflow_result = approved_snapshot.get("workflow_result") or {}
        previous_status = task.status

        self.export_job_repository.update_job(job=job, status=ExportJobStatus.EXPORTING)
        self.task_repository.update_status(task=task, status=TaskStatus.EXPORTING)
        self.audit_log_repository.create_log(
            task_id=task.id,
            export_job_id=job.id,
            event_type=AuditEventType.EXPORT_STARTED,
            outcome=AuditOutcome.SUCCESS,
            summary=f"{job.export_type} export started.",
            details={"export_type": job.export_type},
        )
        try:
            file_path = self._write_export_file(
                export_job_id=job.id,
                export_type=job.export_type,
                task_id=task.id,
                draft=self._build_export_body(workflow_result),
            )
        except Exception as exc:
            # Export failure does not invalidate the stable snapshot, so the
            # task returns to the last safe persisted state and can be retried
            # without losing prior completion state.
            self.task_repository.update_status(task=task, status=previous_status)
            self.export_job_repository.update_job(
                job=job,
                status=ExportJobStatus.FAILED,
                error_message=str(exc),
            )
            self.audit_log_repository.create_log(
                task_id=task.id,
                export_job_id=job.id,
                event_type=AuditEventType.EXPORT_FAILED,
                outcome=AuditOutcome.FAILURE,
                summary=f"{job.export_type} export failed.",
                details={
                    "export_type": job.export_type,
                    "error_message": str(exc),
                },
            )
            raise

        self.task_repository.update_status(task=task, status=TaskStatus.COMPLETED)
        completed_job = self.export_job_repository.update_job(
            job=job,
            status=ExportJobStatus.COMPLETED,
            file_path=str(file_path),
            error_message=None,
        )
        self.audit_log_repository.create_log(
            task_id=task.id,
            export_job_id=job.id,
            event_type=AuditEventType.EXPORT_COMPLETED,
            outcome=AuditOutcome.SUCCESS,
            summary=f"{job.export_type} export completed.",
            details={
                "export_type": job.export_type,
                "file_path": str(file_path),
            },
        )
        # The caller may keep using the returned job after the surrounding
        # session closes, so detach it only after the final audit write.
        self.export_job_repository.session.refresh(completed_job)
        self.export_job_repository.session.expunge(completed_job)
        return completed_job

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

    def _build_export_body(self, workflow_result: dict[str, object]) -> str:
        draft = str(workflow_result.get("draft") or "").strip()
        if draft:
            return draft

        selling_points = [str(item).strip() for item in workflow_result.get("selling_points_copy", []) if str(item).strip()]
        detail_page_copy = str(workflow_result.get("detail_page_copy") or "").strip()
        social_seed_copy = str(workflow_result.get("social_seed_copy") or "").strip()
        risk_notes = [str(item).strip() for item in workflow_result.get("risk_notes", []) if str(item).strip()]

        sections: list[str] = []
        if selling_points:
            sections.append("电商卖点文案\n" + "\n".join(f"- {item}" for item in selling_points))
        if detail_page_copy:
            sections.append("商品详情页文案\n" + detail_page_copy)
        if social_seed_copy:
            sections.append("小红书/种草短文案\n" + social_seed_copy)
        if risk_notes:
            sections.append("风险提醒\n" + "\n".join(f"- {item}" for item in risk_notes))

        return "\n\n".join(sections).strip()
