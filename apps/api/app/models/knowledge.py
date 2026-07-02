from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from pgvector.sqlalchemy import Vector
from sqlmodel import DateTime, Field, SQLModel

EMBEDDING_DIMENSION = 128


class KnowledgeDocumentStatus(StrEnum):
    """Lifecycle states for locally indexed knowledge documents."""

    QUEUED = "queued"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class KnowledgeDocument(SQLModel, table=True):
    """Metadata for a source document that can be retrieved by the pipeline."""

    id: UUID = Field(default_factory=uuid4, primary_key=True, description="Stable knowledge document identifier.")
    title: str = Field(index=True, description="Human-readable source title shown in citations.")
    source_path: str = Field(description="Absolute or repo-local path to the source document.")
    source_type: str = Field(index=True, description="Narrow-domain source category such as faq or brand_guideline.")
    domain: str = Field(index=True, description="Knowledge domain label used to scope retrieval.")
    status: KnowledgeDocumentStatus = Field(
        default=KnowledgeDocumentStatus.QUEUED,
        index=True,
        description="Current indexing lifecycle status.",
    )
    chunk_count: int = Field(default=0, description="Number of indexed chunks currently attached to the document.")
    error_message: str | None = Field(default=None, description="Last indexing failure reason, if any.")
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


class KnowledgeChunk(SQLModel, table=True):
    """Persisted retrieval chunk derived from a source knowledge document."""

    id: UUID = Field(default_factory=uuid4, primary_key=True, description="Stable chunk identifier.")
    document_id: UUID = Field(index=True, description="Owning knowledge document identifier.")
    chunk_index: int = Field(index=True, description="Stable order index of the chunk within the source document.")
    content: str = Field(description="Chunk text used for lexical retrieval and visible citations.")
    retrieval_text: str = Field(
        default="",
        description="Normalized retrieval text used for semantic profile building and vector ranking.",
    )
    embedding_vector: list[float] = Field(
        default_factory=list,
        sa_column=Column(Vector(EMBEDDING_DIMENSION).with_variant(JSON(), "sqlite"), nullable=False),
        description="Dense embedding vector stored for vector-style retrieval ranking.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Creation timestamp in UTC.",
    )
