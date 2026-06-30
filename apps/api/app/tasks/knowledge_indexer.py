from __future__ import annotations

import logging

from sqlmodel import Session

from app.core.db import engine
from app.models import KnowledgeDocumentStatus
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_index_service import KnowledgeIndexService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.index_knowledge_document")
def index_knowledge_document(document_id: str) -> dict[str, str]:
    """Index one registered local knowledge document into retrieval chunks."""

    try:
        with Session(engine) as session:
            repository = KnowledgeRepository(session)
            service = KnowledgeIndexService(repository)
            document = service.index_document(document_id)
            return {
                "document_id": str(document.id),
                "status": document.status,
            }
    except Exception as exc:  # pragma: no cover - worker failure path
        logger.exception("Knowledge indexing failed for %s", document_id)
        with Session(engine) as session:
            repository = KnowledgeRepository(session)
            document = repository.get_document(document_id)
            if document is not None:
                repository.set_document_status(
                    document=document,
                    status=KnowledgeDocumentStatus.FAILED,
                    error_message=str(exc),
                )
        raise
