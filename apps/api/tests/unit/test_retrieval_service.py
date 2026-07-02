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


def test_retrieval_service_uses_document_titles_as_visible_ranking_signals(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    titled_file = tmp_path / "launch-review.md"
    titled_file.write_text(
        "# Internal Notes\n\n"
        "Use the approved workflow when preparing the final review package.\n",
        encoding="utf-8",
    )
    lexical_file = tmp_path / "generic-review.md"
    lexical_file.write_text(
        "# Generic Review\n\n"
        "Launch review steps should stay visible before export.\n",
        encoding="utf-8",
    )

    titled_document = repository.create_document(
        title="Launch Review Checklist",
        source_path=str(titled_file),
        source_type="guide",
        domain="content-ops",
    )
    lexical_document = repository.create_document(
        title="Generic Review Notes",
        source_path=str(lexical_file),
        source_type="guide",
        domain="content-ops",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(titled_document.id)
    index_service.index_document(lexical_document.id)

    hits = RetrievalService(repository).retrieve(
        "Need the launch review checklist before export approval.",
        top_k=3,
        domain="content-ops",
    )

    assert hits
    assert hits[0]["title"] == "Launch Review Checklist"
    assert "title" in hits[0]["reason"].lower()


def test_retrieval_service_matches_simple_word_variants(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    normalized_file = tmp_path / "approvals-guardrails.md"
    normalized_file.write_text(
        "# Guardrails\n\n"
        "Approvals guardrails apply before any launch release.\n",
        encoding="utf-8",
    )
    generic_file = tmp_path / "approval-notes.md"
    generic_file.write_text(
        "# Notes\n\n"
        "Approval notes are visible before export.\n",
        encoding="utf-8",
    )

    normalized_document = repository.create_document(
        title="Approvals Guardrails",
        source_path=str(normalized_file),
        source_type="guide",
        domain="content-ops",
    )
    generic_document = repository.create_document(
        title="Approval Notes",
        source_path=str(generic_file),
        source_type="guide",
        domain="content-ops",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(normalized_document.id)
    index_service.index_document(generic_document.id)

    hits = RetrievalService(repository).retrieve(
        "Need approval guardrail before launch.",
        top_k=3,
        domain="content-ops",
    )

    assert hits
    assert hits[0]["title"] == "Approvals Guardrails"


def test_retrieval_service_matches_minimal_review_synonyms(
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
        top_k=3,
        domain="content-ops",
    )

    assert hits
    assert hits[0]["title"] == "Claims Sign-off Policy"


def test_retrieval_service_can_rank_by_semantic_vector_profile_when_lexical_overlap_is_weak(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    semantic_file = tmp_path / "claims-signoff.md"
    semantic_file.write_text(
        "# Policy\n\n"
        "Every outward-facing promise needs legal sign-off before shipment.\n",
        encoding="utf-8",
    )
    distracting_file = tmp_path / "launch-greenlight.md"
    distracting_file.write_text(
        "# Notes\n\n"
        "Greenlight the launch homepage layout before publishing.\n",
        encoding="utf-8",
    )

    semantic_document = repository.create_document(
        title="Claims Sign-off Policy",
        source_path=str(semantic_file),
        source_type="guide",
        domain="content-ops",
    )
    distracting_document = repository.create_document(
        title="Launch Greenlight Notes",
        source_path=str(distracting_file),
        source_type="guide",
        domain="content-ops",
    )

    class FakeRetrievalProfileProvider:
        provider_name = "fake-semantic-profile"

        def build_chunk_profile(self, *, title: str, content: str, domain: str, source_type: str) -> dict[str, object]:
            if "sign-off" in content:
                return {"retrieval_text": "approval public claim compliance release"}
            return {"retrieval_text": "homepage design visual polish launch"}

        def build_query_profile(self, *, query_text: str, domain: str | None) -> dict[str, object]:
            return {"retrieval_text": "approval public claim compliance release"}

    class FakeEmbeddingService:
        def embed_text(self, text: str) -> list[float]:
            if "approval public claim compliance release" in text:
                return [1.0, 0.0, 0.0]
            if "homepage design visual polish launch" in text:
                return [0.0, 1.0, 0.0]
            return [0.0, 0.0, 1.0]

    index_service = KnowledgeIndexService(
        repository,
        retrieval_profile_provider=FakeRetrievalProfileProvider(),
        embedding_service=FakeEmbeddingService(),
    )
    index_service.index_document(semantic_document.id)
    index_service.index_document(distracting_document.id)

    hits = RetrievalService(
        repository,
        retrieval_profile_provider=FakeRetrievalProfileProvider(),
        embedding_service=FakeEmbeddingService(),
    ).retrieve(
        "Need greenlight for outward-facing promises before release.",
        top_k=3,
        domain="content-ops",
    )

    assert hits
    assert hits[0]["title"] == "Claims Sign-off Policy"
    assert "vector score" in hits[0]["reason"].lower()
