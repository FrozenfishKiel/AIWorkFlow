from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, delete, select

from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus


class KnowledgeRepository:
    """Persistence helpers for knowledge documents and indexed chunks."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_document(
        self,
        *,
        title: str,
        source_path: str,
        source_type: str,
        domain: str,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            title=title,
            source_path=source_path,
            source_type=source_type,
            domain=domain,
        )
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get_document(self, document_id: str | UUID) -> KnowledgeDocument | None:
        return self.session.get(KnowledgeDocument, UUID(str(document_id)))

    def require_document(self, document_id: str | UUID) -> KnowledgeDocument:
        document = self.get_document(document_id)
        if document is None:
            raise LookupError(f"Knowledge document not found: {document_id}")
        return document

    def list_documents(self) -> list[KnowledgeDocument]:
        statement = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
        return list(self.session.exec(statement))

    def set_document_status(
        self,
        *,
        document: KnowledgeDocument,
        status: KnowledgeDocumentStatus,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> KnowledgeDocument:
        document.status = status
        document.error_message = error_message
        if chunk_count is not None:
            document.chunk_count = chunk_count
        document.updated_at = datetime.now(timezone.utc)
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def replace_chunks(self, *, document: KnowledgeDocument, contents: list[str]) -> list[KnowledgeChunk]:
        self.session.exec(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
        chunks = [
            KnowledgeChunk(document_id=document.id, chunk_index=index, content=content)
            for index, content in enumerate(contents)
        ]
        for chunk in chunks:
            self.session.add(chunk)
        self.session.commit()
        for chunk in chunks:
            self.session.refresh(chunk)
        return chunks

    def list_chunks_for_document(self, document_id: str | UUID) -> list[KnowledgeChunk]:
        statement = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == UUID(str(document_id)))
            .order_by(KnowledgeChunk.chunk_index.asc())
        )
        return list(self.session.exec(statement))

    def list_indexed_chunks(self, *, domain: str | None = None) -> list[tuple[KnowledgeDocument, KnowledgeChunk]]:
        statement = (
            select(KnowledgeDocument, KnowledgeChunk)
            .join(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.status == KnowledgeDocumentStatus.INDEXED)
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeChunk.chunk_index.asc())
        )
        if domain:
            statement = statement.where(KnowledgeDocument.domain == domain)
        return list(self.session.exec(statement))
