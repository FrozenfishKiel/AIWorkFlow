from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaskStatus


class TaskCreateRequest(BaseModel):
    """Payload for text and URL task creation."""

    input_type: Literal["text", "url"] = Field(
        description="Submission mode for the current task request.",
    )
    content: str = Field(
        min_length=1,
        description="Raw task text, public URL, or stored file path handled by the API.",
    )
    knowledge_domain: str | None = Field(
        default=None,
        description="Optional knowledge-domain scope used to constrain retrieval to one business area.",
    )


class UnderstandingResult(BaseModel):
    """Structured understanding block shown to reviewers."""

    summary: str = Field(description="Short reviewer-facing summary of the parsed input.")
    audience: list[str] = Field(description="Primary audiences inferred for the task content.")
    key_points: list[str] = Field(description="Main points extracted before generation.")
    risk_points: list[str] = Field(
        default_factory=list,
        description="Reviewer-visible risk flags inferred before generation.",
    )
    uncertain_items: list[str] = Field(
        default_factory=list,
        description="Items the system believes still need confirmation.",
    )
    input_quality: dict[str, object] = Field(
        default_factory=dict,
        description="Input quality markers captured during parsing and normalization, including source-specific metadata.",
    )


class RetrievalHit(BaseModel):
    """RAG hit that remains visible and attributable in the UI."""

    source_id: str = Field(description="Stable knowledge-base identifier for the cited source.")
    title: str = Field(description="Human-readable title shown in the task detail UI.")
    snippet: str = Field(description="Retrieved excerpt that supports the generated result.")
    reason: str = Field(description="Why this source was considered relevant for the task.")


class EvidenceUsedItem(BaseModel):
    """Selected evidence item carried from retrieval into workflow generation."""

    source_id: str = Field(description="Stable knowledge-base identifier for the cited source.")
    title: str = Field(description="Human-readable title shown in the workflow evidence summary.")
    snippet: str = Field(description="Retrieved excerpt that was actually selected into generation context.")
    reason: str = Field(description="Why this evidence item survived retrieval and context selection.")


class WorkflowResult(BaseModel):
    """Structured workflow output for task inspection and export."""

    draft: str = Field(description="Workflow result produced by the async pipeline.")
    review_notes: list[str] = Field(description="Visible checks or cautions attached to the current result.")
    open_questions: list[str] = Field(description="Questions that still require human confirmation.")
    evidence_used: list[EvidenceUsedItem] = Field(
        default_factory=list,
        description="Explicit evidence items the generated draft claims to rely on.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Uncertainties carried forward into the generation result.",
    )
    manual_checks: list[str] = Field(
        default_factory=list,
        description="Checks an operator should complete before reuse or release.",
    )
    context_summary: dict[str, object] = Field(
        default_factory=dict,
        description="Summary of what context sections were assembled for generation.",
    )
    processing_trace: list[str] = Field(
        default_factory=list,
        description="Human-readable trace of the current task pipeline decisions.",
    )

class ApprovedSnapshot(BaseModel):
    """Canonical stable snapshot that downstream export consumes.

    The field name is still legacy, but the ownership boundary is now the same:
    downstream consumers should read this frozen snapshot rather than trying to
    reconstruct the "latest" state from mutable live pipeline fields.
    """

    understanding: UnderstandingResult | None = Field(
        default=None,
        description="Stable understanding payload frozen for downstream consumption.",
    )
    retrieval_hits: list[RetrievalHit] = Field(
        default_factory=list,
        description="Stable retrieval evidence frozen for downstream consumption.",
    )
    workflow_result: WorkflowResult | None = Field(
        default=None,
        description="Stable workflow result used for export generation.",
    )


class ExportJobCreateRequest(BaseModel):
    """Payload used to request an export from a completed task snapshot."""

    task_id: UUID = Field(description="Completed task identifier to export.")
    export_type: Literal["markdown", "structured_text"] = Field(
        description="Export format requested by the user.",
    )


class ExportJobRead(BaseModel):
    """API response shape for export job status and artifact lookup."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Stable export job identifier.")
    task_id: UUID = Field(description="Task whose approved snapshot is being exported.")
    export_type: str = Field(description="Requested export format.")
    status: str = Field(description="Current export lifecycle status.")
    file_path: str | None = Field(default=None, description="Generated artifact path when complete.")
    error_message: str | None = Field(default=None, description="Latest export failure detail.")
    created_at: datetime = Field(description="UTC timestamp when the export job was created.")
    updated_at: datetime = Field(description="UTC timestamp when the export job last changed.")


class TaskRead(BaseModel):
    """API response shape for task summaries and details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Stable task identifier returned to the client.")
    input_type: str = Field(description="Original task submission mode.")
    content: str = Field(description="Stored task payload or normalized source reference.")
    knowledge_domain: str | None = Field(
        default=None,
        description="Optional retrieval-domain scope persisted with the task.",
    )
    status: TaskStatus = Field(description="Current lifecycle status for the async task.")
    current_stage: str = Field(description="Most recent pipeline stage written for UI polling.")
    error_message: str | None = Field(
        default=None,
        description="Latest failure detail when the task enters a failed state.",
    )
    understanding: UnderstandingResult | None = None
    retrieval_hits: list[RetrievalHit] = Field(
        default_factory=list,
        description="Visible retrieval evidence shown in the task detail view.",
    )
    workflow_result: WorkflowResult | None = None
    approved_snapshot: ApprovedSnapshot | None = Field(
        default=None,
        description="Canonical stable snapshot that export and other downstream flows must consume.",
    )
    created_at: datetime = Field(description="UTC timestamp when the task was created.")
    updated_at: datetime = Field(description="UTC timestamp when the task last changed.")
