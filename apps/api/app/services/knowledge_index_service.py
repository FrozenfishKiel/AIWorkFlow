from __future__ import annotations

from pathlib import Path
from typing import Iterable
from uuid import UUID

from app.models import KnowledgeDocument, KnowledgeDocumentStatus
from app.repositories.knowledge_repository import KnowledgeRepository


class KnowledgeIndexService:
    """Reads local source files, chunks them, and persists retrieval-ready records."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    def index_document(self, document_id: str | UUID) -> KnowledgeDocument:
        """Index one registered local source file into retrieval chunks."""

        document = self.repository.require_document(document_id)
        self.repository.set_document_status(document=document, status=KnowledgeDocumentStatus.INDEXING, error_message=None)
        source_text = Path(document.source_path).read_text(encoding="utf-8")
        chunks = list(self._chunk_text(source_text))
        self.repository.replace_chunks(document=document, contents=chunks)
        return self.repository.set_document_status(
            document=document,
            status=KnowledgeDocumentStatus.INDEXED,
            chunk_count=len(chunks),
            error_message=None,
        )

    def _chunk_text(self, source_text: str) -> Iterable[str]:
        """Split cleaned source text into reviewer-sized retrieval chunks."""

        paragraphs = [paragraph.strip() for paragraph in source_text.split("\n\n") if paragraph.strip()]
        buffer: list[str] = []
        current_length = 0
        for paragraph in paragraphs:
            if current_length + len(paragraph) > 400 and buffer:
                yield "\n\n".join(buffer)
                buffer = [paragraph]
                current_length = len(paragraph)
                continue
            buffer.append(paragraph)
            current_length += len(paragraph)

        if buffer:
            yield "\n\n".join(buffer)
