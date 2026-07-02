from pathlib import Path

from sqlmodel import Session

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_index_service import KnowledgeIndexService


def test_knowledge_index_service_indexes_local_markdown_into_chunks(
    session: Session,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "brand-guideline.md"
    source_file.write_text(
        "# Brand Guideline\n\n"
        "Use a practical tone.\n\n"
        "Do not make exaggerated growth claims.\n\n"
        "Keep reviewer-visible citations in the final output.\n",
        encoding="utf-8",
    )

    repository = KnowledgeRepository(session)
    document = repository.create_document(
        title="Brand Guideline",
        source_path=str(source_file),
        source_type="brand_guideline",
        domain="brand",
    )

    service = KnowledgeIndexService(repository)
    indexed_document = service.index_document(document.id)
    chunks = repository.list_chunks_for_document(document.id)

    assert indexed_document.status == "indexed"
    assert indexed_document.chunk_count == len(chunks)
    assert indexed_document.chunk_count > 0
    assert "practical tone" in chunks[0].content.lower()
    assert chunks[0].retrieval_text
    assert chunks[0].embedding_vector
    assert any(value != 0 for value in chunks[0].embedding_vector)
