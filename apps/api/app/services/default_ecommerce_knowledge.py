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
    {
        "title": "商品资料模板",
        "filename": "商品资料模板.md",
        "source_type": "product_template",
        "domain": "ecommerce",
    },
    {
        "title": "黑咖啡浓缩液事实卡",
        "filename": "黑咖啡浓缩液-事实卡.md",
        "source_type": "product_fact_card",
        "domain": "ecommerce",
    },
    {
        "title": "便携挂脖小风扇事实卡",
        "filename": "便携挂脖小风扇-事实卡.md",
        "source_type": "product_fact_card",
        "domain": "ecommerce",
    },
    {
        "title": "洁面个护清洁事实卡",
        "filename": "洁面个护清洁-事实卡.md",
        "source_type": "category_fact_card",
        "domain": "ecommerce",
    },
    {
        "title": "轻食零食事实卡",
        "filename": "轻食零食-事实卡.md",
        "source_type": "category_fact_card",
        "domain": "ecommerce",
    },
    {
        "title": "宠物清洁事实卡",
        "filename": "宠物清洁-事实卡.md",
        "source_type": "category_fact_card",
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

        if _default_document_needs_reindex(
            repository=repository,
            index_service=index_service,
            document=document,
            source_path=source_path,
        ):
            index_service.index_document(document.id)


def _default_document_needs_reindex(
    *,
    repository: KnowledgeRepository,
    index_service: KnowledgeIndexService,
    document,
    source_path: Path,
) -> bool:
    if document.status != KnowledgeDocumentStatus.INDEXED or document.chunk_count <= 0:
        return True

    expected_chunk_texts = index_service.build_chunk_texts_from_path(source_path)
    actual_chunks = repository.list_chunks_for_document(document.id)

    if document.chunk_count != len(expected_chunk_texts) or len(actual_chunks) != len(expected_chunk_texts):
        return True

    for actual_chunk, expected_chunk_text in zip(actual_chunks, expected_chunk_texts, strict=False):
        if actual_chunk.content != expected_chunk_text:
            return True
        if not actual_chunk.retrieval_text.strip():
            return True
        if not actual_chunk.embedding_vector:
            return True

    return False
