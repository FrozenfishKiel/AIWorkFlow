from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlmodel import DateTime, Field, SQLModel


class ExportJobStatus(StrEnum):
    """Lifecycle states for export materialization jobs."""

    QUEUED = "queued"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJob(SQLModel, table=True):
    """Tracks export requests and the generated artifact location."""

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Stable export job identifier returned to the client.",
    )
    task_id: UUID = Field(
        index=True,
        description="Task identifier whose approved snapshot is being exported.",
    )
    export_type: str = Field(
        index=True,
        description="Export format such as markdown or structured_text.",
    )
    status: ExportJobStatus = Field(
        default=ExportJobStatus.QUEUED,
        index=True,
        description="Current export lifecycle status.",
    )
    file_path: str | None = Field(
        default=None,
        description="Generated artifact path when export completes successfully.",
    )
    error_message: str | None = Field(
        default=None,
        description="Failure reason captured when export generation fails.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Creation timestamp in UTC.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Last update timestamp in UTC.",
    )
