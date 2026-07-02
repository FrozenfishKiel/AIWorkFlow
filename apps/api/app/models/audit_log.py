from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import DateTime, Field, SQLModel


class AuditEventType(StrEnum):
    """Task-level events we want to replay later as a readable timeline."""

    PIPELINE_COMPLETED = "pipeline_completed"
    SNAPSHOT_PERSISTED = "snapshot_persisted"
    EXPORT_CREATED = "export_created"
    EXPORT_STARTED = "export_started"
    EXPORT_COMPLETED = "export_completed"
    EXPORT_FAILED = "export_failed"


class AuditOutcome(StrEnum):
    """Small success/failure vocabulary for the first audit slice."""

    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(SQLModel, table=True):
    """One row in the task action ledger.

    Think of this as a single line in the system's running notebook:
    which task did something, what happened, was it successful, and what
    extra details should the UI show in the timeline.
    """

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Stable identifier for one audit row.",
    )
    task_id: UUID = Field(
        index=True,
        description="The task whose action timeline this row belongs to.",
    )
    export_job_id: UUID | None = Field(
        default=None,
        index=True,
        description="Optional export job reference for export-related actions.",
    )
    event_type: AuditEventType = Field(
        index=True,
        description="What happened, such as pipeline completion or export completion.",
    )
    outcome: AuditOutcome = Field(
        index=True,
        description="Whether the recorded action succeeded or failed.",
    )
    summary: str = Field(
        description="One short sentence the UI can show directly in the timeline.",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Extra structured context kept alongside the human-readable summary.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When this action was recorded in UTC.",
    )
