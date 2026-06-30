from pathlib import Path

from sqlmodel import Session

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.retrieval_service import RetrievalService


def test_retrieval_regression_prefers_domain_scoped_guidance_for_launch_claims(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    brand_file = tmp_path / "brand.md"
    brand_file.write_text(
        "# Brand\n\n"
        "Use customer language and keep tone practical.\n",
        encoding="utf-8",
    )
    compliance_file = tmp_path / "compliance.md"
    compliance_file.write_text(
        "# Compliance\n\n"
        "Launch claims require compliance approval and visible review notes.\n",
        encoding="utf-8",
    )

    brand_document = repository.create_document(
        title="Brand Guide",
        source_path=str(brand_file),
        source_type="guide",
        domain="brand",
    )
    compliance_document = repository.create_document(
        title="Compliance Guide",
        source_path=str(compliance_file),
        source_type="guide",
        domain="compliance",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(brand_document.id)
    index_service.index_document(compliance_document.id)

    hits = RetrievalService(repository).retrieve(
        "Create launch copy with compliance approval before publishing claims.",
        domain="compliance",
        top_k=3,
    )

    assert hits
    assert hits[0]["title"] == "Compliance Guide"
