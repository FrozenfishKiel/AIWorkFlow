from __future__ import annotations

from pathlib import Path
import re
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
        chunk_records = self.build_chunk_records_from_path(
            title=document.title,
            source_path=document.source_path,
            domain=document.domain,
            source_type=document.source_type,
        )
        self.repository.replace_chunk_records(document=document, chunk_records=chunk_records)
        return self.repository.set_document_status(
            document=document,
            status=KnowledgeDocumentStatus.INDEXED,
            chunk_count=len(chunk_records),
            error_message=None,
        )

    def build_chunk_texts_from_path(self, source_path: str | Path) -> list[str]:
        source_text = Path(source_path).read_text(encoding="utf-8")
        return self.build_chunk_texts(source_text)

    def build_chunk_texts(self, source_text: str) -> list[str]:
        return list(self._chunk_text(source_text))

    def build_chunk_records_from_path(
        self,
        *,
        title: str,
        source_path: str | Path,
        domain: str,
        source_type: str,
    ) -> list[dict[str, object]]:
        source_text = Path(source_path).read_text(encoding="utf-8")
        return self.build_chunk_records(
            title=title,
            source_text=source_text,
            domain=domain,
            source_type=source_type,
        )

    def build_chunk_records(
        self,
        *,
        title: str,
        source_text: str,
        domain: str,
        source_type: str,
    ) -> list[dict[str, object]]:
        chunk_records: list[dict[str, object]] = []
        for chunk in self.build_chunk_texts(source_text):
            profile = self.retrieval_profile_provider.build_chunk_profile(
                title=title,
                content=chunk,
                domain=domain,
                source_type=source_type,
            )
            retrieval_text = str(profile.get("retrieval_text") or chunk)
            chunk_records.append(
                {
                    "content": chunk,
                    "retrieval_text": retrieval_text,
                    "embedding_vector": self.embedding_service.embed_text(retrieval_text),
                }
            )
        return chunk_records

    def _chunk_text(self, source_text: str) -> Iterable[str]:
        """Split cleaned source text into structure-aware reviewer-sized chunks."""

        max_chunk_chars = 220
        heading_stack: list[str] = []

        for block in self._iter_structured_blocks(source_text):
            block_type = str(block["type"])
            block_text = str(block["text"]).strip()
            if not block_text:
                continue

            if block_type == "heading":
                level = int(block["level"])
                heading_stack[:] = heading_stack[: max(level - 1, 0)]
                heading_stack.append(block_text)
                continue

            contextual_headings = heading_stack[-2:]
            for chunk_body in self._split_block(block_type=block_type, block_text=block_text, max_chunk_chars=max_chunk_chars):
                chunk_text = "\n".join([*contextual_headings, chunk_body]).strip()
                if chunk_text:
                    yield chunk_text

    def _split_block(self, *, block_type: str, block_text: str, max_chunk_chars: int) -> Iterable[str]:
        if block_type == "list_item":
            yield from self._split_long_text(block_text, max_chunk_chars=max_chunk_chars)
            return

        for paragraph_part in self._split_long_text(block_text, max_chunk_chars=max_chunk_chars):
            yield paragraph_part

    def _split_long_text(self, block_text: str, *, max_chunk_chars: int) -> Iterable[str]:
        if len(block_text) <= max_chunk_chars:
            yield block_text
            return

        sentence_parts = [part.strip() for part in re.split(r"(?<=[。！？.!?；;])\s*", block_text) if part.strip()]
        if len(sentence_parts) <= 1:
            for start in range(0, len(block_text), max_chunk_chars):
                yield block_text[start : start + max_chunk_chars].strip()
            return

        buffer = ""
        for sentence in sentence_parts:
            candidate = sentence if not buffer else f"{buffer} {sentence}"
            if buffer and len(candidate) > max_chunk_chars:
                yield buffer
                buffer = sentence
                continue
            buffer = candidate

        if buffer:
            yield buffer

    def _iter_structured_blocks(self, source_text: str) -> Iterable[dict[str, object]]:
        """Parse markdown-like text into headings, paragraphs, and list-item blocks."""

        lines = source_text.splitlines()
        paragraph_lines: list[str] = []
        list_pattern = re.compile(r"^(?:[-*]\s+|\d+\.\s+)(.+)$")

        def flush_paragraph() -> str | None:
            nonlocal paragraph_lines
            if not paragraph_lines:
                return None
            paragraph = " ".join(line.strip() for line in paragraph_lines if line.strip()).strip()
            paragraph_lines = []
            return paragraph or None

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                paragraph = flush_paragraph()
                if paragraph:
                    yield {"type": "paragraph", "text": paragraph}
                continue

            if stripped.startswith("#"):
                paragraph = flush_paragraph()
                if paragraph:
                    yield {"type": "paragraph", "text": paragraph}

                level = len(stripped) - len(stripped.lstrip("#"))
                heading = stripped[level:].strip()
                if heading:
                    yield {"type": "heading", "level": level, "text": heading}
                continue

            list_match = list_pattern.match(stripped)
            if list_match:
                paragraph = flush_paragraph()
                if paragraph:
                    yield {"type": "paragraph", "text": paragraph}

                yield {"type": "list_item", "text": list_match.group(1).strip()}
                continue

            paragraph_lines.append(stripped)

        paragraph = flush_paragraph()
        if paragraph:
            yield {"type": "paragraph", "text": paragraph}
