from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import KnowledgeDocumentCreateRequest, KnowledgeDocumentRead
from app.tasks.knowledge_indexer import index_knowledge_document

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/index-local", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
def index_local_document(
    payload: KnowledgeDocumentCreateRequest,
    session: Session = Depends(get_session),
) -> KnowledgeDocumentRead:
    """Register a local source file and enqueue async indexing for retrieval."""

    source_path = Path(payload.source_path)
    if not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source file not found.")

    repository = KnowledgeRepository(session)
    document = repository.create_document(
        title=payload.title,
        source_path=str(source_path),
        source_type=payload.source_type,
        domain=payload.domain,
    )
    index_knowledge_document.delay(str(document.id))
    return KnowledgeDocumentRead.model_validate(document)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentRead)
def get_knowledge_document(document_id: UUID, session: Session = Depends(get_session)) -> KnowledgeDocumentRead:
    """Return the current indexing state for one registered knowledge document."""

    repository = KnowledgeRepository(session)
    document = repository.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found.")
    return KnowledgeDocumentRead.model_validate(document)
