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


def test_retrieval_regression_keeps_title_match_visible_for_launch_review_queries(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    title_match_file = tmp_path / "launch-review-checklist.md"
    title_match_file.write_text(
        "# Checklist\n\n"
        "Follow the reviewed workflow package before final export.\n",
        encoding="utf-8",
    )
    generic_file = tmp_path / "generic-launch-review.md"
    generic_file.write_text(
        "# Review\n\n"
        "Launch review requires visible export notes and reviewer confirmation.\n",
        encoding="utf-8",
    )

    title_match_document = repository.create_document(
        title="Launch Review Checklist",
        source_path=str(title_match_file),
        source_type="guide",
        domain="content-ops",
    )
    generic_document = repository.create_document(
        title="Generic Launch Review",
        source_path=str(generic_file),
        source_type="guide",
        domain="content-ops",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(title_match_document.id)
    index_service.index_document(generic_document.id)

    hits = RetrievalService(repository).retrieve(
        "Need the launch review checklist before export approval.",
        domain="content-ops",
        top_k=3,
    )

    assert hits
    assert hits[0]["title"] == "Launch Review Checklist"


def test_retrieval_regression_handles_basic_approval_language_variants(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    signoff_file = tmp_path / "claims-signoff.md"
    signoff_file.write_text(
        "# Policy\n\n"
        "Every externally visible claim needs legal sign-off before shipment.\n",
        encoding="utf-8",
    )
    approval_file = tmp_path / "launch-approval.md"
    approval_file.write_text(
        "# Approval\n\n"
        "Approval notes before launch export review.\n",
        encoding="utf-8",
    )

    signoff_document = repository.create_document(
        title="Claims Sign-off Policy",
        source_path=str(signoff_file),
        source_type="guide",
        domain="content-ops",
    )
    approval_document = repository.create_document(
        title="Launch Approval Notes",
        source_path=str(approval_file),
        source_type="guide",
        domain="content-ops",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(signoff_document.id)
    index_service.index_document(approval_document.id)

    hits = RetrievalService(repository).retrieve(
        "Need approval for public claims before launch.",
        domain="content-ops",
        top_k=3,
    )

    assert hits
    assert hits[0]["title"] == "Claims Sign-off Policy"
