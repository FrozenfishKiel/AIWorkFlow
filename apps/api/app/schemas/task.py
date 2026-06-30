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
    title: str = Field(description="Human-readable title shown in the review UI.")
    snippet: str = Field(description="Retrieved excerpt that supports the generated result.")
    reason: str = Field(description="Why this source was considered relevant for the task.")


class WorkflowResult(BaseModel):
    """Structured workflow output for review and export."""

    draft: str = Field(description="Draft workflow result produced before human review.")
    review_notes: list[str] = Field(description="Reviewer-visible checks or cautions for the draft.")
    open_questions: list[str] = Field(description="Questions that still require human confirmation.")
    evidence_used: list[dict[str, str]] = Field(
        default_factory=list,
        description="Explicit evidence items the generated draft claims to rely on.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Uncertainties carried forward into the generation result.",
    )
    manual_checks: list[str] = Field(
        default_factory=list,
        description="Checks the reviewer should complete before approval.",
    )
    context_summary: dict[str, object] = Field(
        default_factory=dict,
        description="Summary of what context sections were assembled for generation.",
    )
    processing_trace: list[str] = Field(
        default_factory=list,
        description="Human-readable trace of the current task pipeline decisions.",
    )


class ReviewDecision(str):
    """String literal wrapper kept simple for schema readability."""


class ReviewSnapshot(BaseModel):
    """Persisted reviewer-side snapshot for the current task."""

    decision: Literal["in_review", "approved", "rejected"] = Field(
        description="Current human review decision state for the task.",
    )
    reviewer_note: str | None = Field(
        default=None,
        description="Reviewer note explaining the current review action.",
    )
    rejection_reason: str | None = Field(
        default=None,
        description="Reason captured when the task is rejected.",
    )
    rerun_reason: str | None = Field(
        default=None,
        description="Reason captured when the rejected task is sent back for regeneration.",
    )
    not_adopted_items: list[str] = Field(
        default_factory=list,
        description="Explicit items the reviewer decided not to adopt.",
    )
    edited_understanding: UnderstandingResult | None = Field(
        default=None,
        description="Reviewer-adjusted understanding result kept for audit and export.",
    )
    edited_retrieval_hits: list[RetrievalHit] = Field(
        default_factory=list,
        description="Reviewer-adjusted retrieval evidence that replaces the generated defaults.",
    )
    edited_workflow_result: WorkflowResult | None = Field(
        default=None,
        description="Reviewer-adjusted workflow result used by downstream export flows.",
    )


class ApprovedSnapshot(BaseModel):
    """Canonical reviewed snapshot that downstream export consumes.

    This schema exists to make the ownership boundary explicit: once a task is
    approved, downstream consumers should read this snapshot rather than trying
    to reconstruct the "latest" state from mutable review or generation fields.
    """

    understanding: UnderstandingResult | None = Field(
        default=None,
        description="Approved understanding payload after review decisions are applied.",
    )
    retrieval_hits: list[RetrievalHit] = Field(
        default_factory=list,
        description="Approved reviewer-visible retrieval evidence.",
    )
    workflow_result: WorkflowResult | None = Field(
        default=None,
        description="Approved workflow result used for export generation.",
    )


class ReviewUpdateRequest(BaseModel):
    """Payload used to save reviewer edits while a task is being reviewed."""

    edited_understanding: UnderstandingResult | None = Field(
        default=None,
        description="Optional reviewer replacement for the understanding result.",
    )
    edited_retrieval_hits: list[RetrievalHit] | None = Field(
        default=None,
        description="Optional reviewer replacement list for retrieval hits. Null keeps the current value.",
    )
    edited_workflow_result: WorkflowResult | None = Field(
        default=None,
        description="Optional reviewer replacement for the generated workflow result.",
    )
    not_adopted_items: list[str] = Field(
        default_factory=list,
        description="Items the reviewer explicitly chooses not to adopt.",
    )
    reviewer_note: str | None = Field(
        default=None,
        description="Free-text reviewer note for the saved review state.",
    )


class ReviewRejectRequest(BaseModel):
    """Payload for rejecting a task during review."""

    rejection_reason: str = Field(
        min_length=1,
        description="Human-readable reason explaining why the task was rejected.",
    )


class ReviewRerunRequest(BaseModel):
    """Payload for sending a rejected task back through the async pipeline."""

    rerun_reason: str = Field(
        min_length=1,
        description="Human-readable reason explaining what should change on rerun.",
    )


class ExportJobCreateRequest(BaseModel):
    """Payload used to request an export from an approved task."""

    task_id: UUID = Field(description="Approved task identifier to export.")
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
        description="Visible retrieval evidence shown to the reviewer.",
    )
    workflow_result: WorkflowResult | None = None
    review: ReviewSnapshot | None = Field(
        default=None,
        description="Current persisted human review state, including editable reviewer overrides before approval.",
    )
    approved_snapshot: ApprovedSnapshot | None = Field(
        default=None,
        description="Canonical reviewed snapshot that export and other downstream flows must consume after approval.",
    )
    created_at: datetime = Field(description="UTC timestamp when the task was created.")
    updated_at: datetime = Field(description="UTC timestamp when the task last changed.")
