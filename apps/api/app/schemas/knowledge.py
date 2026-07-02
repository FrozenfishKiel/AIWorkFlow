from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import KnowledgeDocumentStatus


class KnowledgeDocumentCreateRequest(BaseModel):
    """Payload used to register a local source file for indexing."""

    title: str = Field(min_length=1, description="Human-readable document title.")
    source_path: str = Field(min_length=1, description="Absolute or repo-local path to the source file.")
    source_type: str = Field(min_length=1, description="Source category such as faq or brand_guideline.")
    domain: str = Field(min_length=1, description="Knowledge domain label used during retrieval.")


class KnowledgeDocumentRead(BaseModel):
    """API response shape for knowledge document indexing state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Stable knowledge document identifier.")
    title: str = Field(description="Human-readable source title.")
    source_path: str = Field(description="Stored source path.")
    source_type: str = Field(description="Source category label.")
    domain: str = Field(description="Knowledge domain label.")
    status: KnowledgeDocumentStatus = Field(description="Current indexing lifecycle status.")
    chunk_count: int = Field(description="Number of indexed chunks attached to the document.")
    error_message: str | None = Field(default=None, description="Latest indexing failure detail.")
    created_at: datetime = Field(description="UTC timestamp when the document was registered.")
    updated_at: datetime = Field(description="UTC timestamp when the document last changed.")


class KnowledgeChunkPreviewRead(BaseModel):
    """Reviewer-visible preview for one indexed chunk."""

    chunk_index: int = Field(description="Stable chunk order inside the source document.")
    content_preview: str = Field(description="Readable preview content from the indexed chunk.")


class KnowledgeDocumentDetailRead(KnowledgeDocumentRead):
    """Richer knowledge document detail used by the task console."""

    chunk_preview: list[KnowledgeChunkPreviewRead] = Field(
        default_factory=list,
        description="Indexed chunk previews shown to reviewers for quick inspection.",
    )
