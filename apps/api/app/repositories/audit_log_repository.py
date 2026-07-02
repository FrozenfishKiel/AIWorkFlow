from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from app.models import AuditEventType, AuditLog, AuditOutcome


class AuditLogRepository:
    """Persistence helper for the task action ledger."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_log(
        self,
        *,
        task_id: UUID,
        event_type: AuditEventType,
        outcome: AuditOutcome,
        summary: str,
        details: dict[str, object] | None = None,
        export_job_id: UUID | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            task_id=task_id,
            export_job_id=export_job_id,
            event_type=event_type,
            outcome=outcome,
            summary=summary,
            details=details or {},
        )
        self.session.add(audit_log)
        self.session.commit()
        self.session.refresh(audit_log)
        return audit_log

    def list_for_task(self, task_id: str | UUID) -> list[AuditLog]:
        statement = (
            select(AuditLog)
            .where(AuditLog.task_id == UUID(str(task_id)))
            .order_by(AuditLog.created_at.desc())
        )
        return list(self.session.exec(statement))
