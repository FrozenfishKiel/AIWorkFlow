from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.core.settings import get_settings
from app.models import KnowledgeDocumentStatus
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_index_service import KnowledgeIndexService


DEFAULT_ECOMMERCE_DOCUMENTS = (
    {
        "title": "品牌语气规范",
        "filename": "品牌语气规范.md",
        "source_type": "brand_guide",
        "domain": "ecommerce",
    },
    {
        "title": "平台文案差异",
        "filename": "平台文案差异.md",
        "source_type": "platform_guide",
        "domain": "ecommerce",
    },
    {
        "title": "历史优稿参考",
        "filename": "历史优稿参考.md",
        "source_type": "high_performing_examples",
        "domain": "ecommerce",
    },
)


def ensure_default_ecommerce_knowledge(session: Session) -> None:
    settings = get_settings()
    repository = KnowledgeRepository(session)
    index_service = KnowledgeIndexService(repository)
    source_root = settings.repo_root / "knowledge-base" / "02-curated-notes" / "ecommerce"
    existing_documents = {
        Path(document.source_path).resolve(): document
        for document in repository.list_documents()
    }

    for document_spec in DEFAULT_ECOMMERCE_DOCUMENTS:
        source_path = (source_root / document_spec["filename"]).resolve()
        document = existing_documents.get(source_path)
        if document is None:
            document = repository.create_document(
                title=document_spec["title"],
                source_path=str(source_path),
                source_type=document_spec["source_type"],
                domain=document_spec["domain"],
            )

        if document.status != KnowledgeDocumentStatus.INDEXED or document.chunk_count <= 0:
            index_service.index_document(document.id)
