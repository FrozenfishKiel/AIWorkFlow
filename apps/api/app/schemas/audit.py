from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import AuditEventType, AuditOutcome


class AuditLogRead(BaseModel):
    """API response shape for one task timeline row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Stable identifier for one audit row.")
    task_id: UUID = Field(description="Task identifier this audit row belongs to.")
    export_job_id: UUID | None = Field(
        default=None,
        description="Optional export job identifier for export-related actions.",
    )
    event_type: AuditEventType = Field(description="What kind of action was recorded.")
    outcome: AuditOutcome = Field(description="Whether the action succeeded or failed.")
    summary: str = Field(description="One short sentence the UI can show directly.")
    details: dict[str, object] = Field(
        default_factory=dict,
        description="Extra structured information kept with this audit row.",
    )
    created_at: datetime = Field(description="UTC timestamp for the recorded action.")
