from __future__ import annotations

from sqlmodel import Session

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.default_ecommerce_knowledge import ensure_default_ecommerce_knowledge


def test_default_ecommerce_knowledge_seed_registers_indexed_documents_once(
    session: Session,
) -> None:
    repository = KnowledgeRepository(session)

    ensure_default_ecommerce_knowledge(session)
    ensure_default_ecommerce_knowledge(session)

    documents = repository.list_documents()
    assert {document.title for document in documents} >= {
        "品牌语气规范",
        "平台文案差异",
        "历史优稿参考",
    }
    assert all(document.status == "indexed" for document in documents)
    assert len(documents) == len({document.source_path for document in documents})
