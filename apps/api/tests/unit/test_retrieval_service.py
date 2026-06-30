from pathlib import Path

from sqlmodel import Session

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.retrieval_service import RetrievalService


def test_retrieval_service_filters_hits_by_requested_domain(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    brand_file = tmp_path / "brand.md"
    brand_file.write_text(
        "# Brand\n\n"
        "Launch messaging must sound practical and reviewer-friendly.\n",
        encoding="utf-8",
    )
    legal_file = tmp_path / "legal.md"
    legal_file.write_text(
        "# Legal\n\n"
        "Every launch claim needs legal approval and visible compliance notes.\n",
        encoding="utf-8",
    )

    brand_document = repository.create_document(
        title="Brand Guide",
        source_path=str(brand_file),
        source_type="guide",
        domain="brand",
    )
    legal_document = repository.create_document(
        title="Legal Guide",
        source_path=str(legal_file),
        source_type="guide",
        domain="legal",
    )
    index_service = KnowledgeIndexService(repository)
    index_service.index_document(brand_document.id)
    index_service.index_document(legal_document.id)

    retrieval_service = RetrievalService(repository)
    hits = retrieval_service.retrieve(
        "Create launch messaging with compliance notes and legal approval.",
        top_k=5,
        domain="legal",
    )

    assert hits
    assert {hit["title"] for hit in hits} == {"Legal Guide"}
    assert all("legal" in hit["reason"].lower() for hit in hits)


def test_retrieval_service_prefers_phrase_and_term_dense_matches(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    broad_file = tmp_path / "broad.md"
    broad_file.write_text(
        "# Broad\n\n"
        "Launch teams need practical review steps and visible citations for export.\n",
        encoding="utf-8",
    )
    dense_file = tmp_path / "dense.md"
    dense_file.write_text(
        "# Dense\n\n"
        "Visible citations are mandatory before export. Manual review is mandatory before export.\n",
        encoding="utf-8",
    )

    broad_document = repository.create_document(
        title="Broad Guide",
        source_path=str(broad_file),
        source_type="guide",
        domain="content-ops",
    )
    dense_document = repository.create_document(
        title="Dense Guide",
        source_path=str(dense_file),
        source_type="guide",
        domain="content-ops",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(broad_document.id)
    index_service.index_document(dense_document.id)

    hits = RetrievalService(repository).retrieve(
        "Visible citations are mandatory before export and manual review is mandatory before export.",
        top_k=3,
        domain="content-ops",
    )

    assert hits
    assert hits[0]["title"] == "Dense Guide"
    assert "score" in hits[0]["reason"].lower()
