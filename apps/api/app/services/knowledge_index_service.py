from __future__ import annotations

from pathlib import Path
from typing import Iterable
from uuid import UUID

from app.core.settings import get_settings
from app.models import KnowledgeDocument, KnowledgeDocumentStatus
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embedding_service import HashEmbeddingService
from app.services.retrieval_profile_provider import (
    RetrievalProfileProvider,
    build_retrieval_profile_provider,
)


class KnowledgeIndexService:
    """Reads local source files, chunks them, and persists retrieval-ready records."""

    def __init__(
        self,
        repository: KnowledgeRepository,
        *,
        retrieval_profile_provider: RetrievalProfileProvider | None = None,
        embedding_service: HashEmbeddingService | None = None,
    ) -> None:
        self.repository = repository
        self.retrieval_profile_provider = retrieval_profile_provider or build_retrieval_profile_provider()
        settings = get_settings()
        self.embedding_service = embedding_service or HashEmbeddingService(
            dimension=settings.retrieval_embedding_dimension,
        )

    def index_document(self, document_id: str | UUID) -> KnowledgeDocument:
        """Index one registered local source file into retrieval chunks."""

        document = self.repository.require_document(document_id)
        self.repository.set_document_status(document=document, status=KnowledgeDocumentStatus.INDEXING, error_message=None)
        source_text = Path(document.source_path).read_text(encoding="utf-8")
        chunks = list(self._chunk_text(source_text))
        chunk_records = []
        for chunk in chunks:
            profile = self.retrieval_profile_provider.build_chunk_profile(
                title=document.title,
                content=chunk,
                domain=document.domain,
                source_type=document.source_type,
            )
            retrieval_text = str(profile.get("retrieval_text") or chunk)
            chunk_records.append(
                {
                    "content": chunk,
                    "retrieval_text": retrieval_text,
                    "embedding_vector": self.embedding_service.embed_text(retrieval_text),
                }
            )
        self.repository.replace_chunk_records(document=document, chunk_records=chunk_records)
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
