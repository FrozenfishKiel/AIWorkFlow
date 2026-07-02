from pathlib import Path

import pytest
from sqlmodel import Session

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.retrieval_service import RetrievalService


def _index_document(
    repository: KnowledgeRepository,
    *,
    tmp_path: Path,
    file_name: str,
    title: str,
    content: str,
    domain: str = "content-ops",
) -> None:
    source_file = tmp_path / file_name
    source_file.write_text(content, encoding="utf-8")
    document = repository.create_document(
        title=title,
        source_path=str(source_file),
        source_type="guide",
        domain=domain,
    )
    KnowledgeIndexService(repository).index_document(document.id)


def test_retrieval_diagnostics_baseline_title_signal_is_now_stable(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="launch-review-checklist.md",
        title="Launch Review Checklist",
        content=(
            "# Checklist\n\n"
            "Follow the approved workflow package before final export.\n"
        ),
    )
    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="generic-launch-review.md",
        title="Generic Launch Review",
        content=(
            "# Review\n\n"
            "Launch review requires visible export notes and reviewer confirmation.\n"
        ),
    )

    hits = RetrievalService(repository).retrieve(
        "Need the launch review checklist before export approval.",
        domain="content-ops",
        top_k=3,
    )

    assert hits, "Expected at least one retrieval hit for the baseline diagnostic case."
    assert hits[0]["title"] == "Launch Review Checklist"
    assert "title signals" in hits[0]["reason"].lower()


def test_retrieval_diagnostics_baseline_domain_filter_is_stable(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="brand.md",
        title="Brand Voice Guide",
        content=(
            "# Brand\n\n"
            "Launch copy should stay practical and customer-facing.\n"
        ),
        domain="brand",
    )
    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="compliance.md",
        title="Compliance Checklist",
        content=(
            "# Compliance\n\n"
            "Every launch claim requires compliance approval before export.\n"
        ),
        domain="compliance",
    )

    hits = RetrievalService(repository).retrieve(
        "Need compliance approval before exporting launch claims.",
        domain="compliance",
        top_k=3,
    )

    assert hits, "Expected compliance-scoped retrieval to return visible evidence."
    assert {hit["title"] for hit in hits} == {"Compliance Checklist"}


@pytest.mark.xfail(
    reason=(
        "Known limit: current retrieval is still lexical-only and cannot reliably bridge "
        "semantic synonyms such as 'approval' versus 'sign-off'."
    ),
    strict=True,
)
def test_retrieval_diagnostics_known_limit_semantic_synonyms(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="signoff-policy.md",
        title="Claims Sign-off Policy",
        content=(
            "# Policy\n\n"
            "Every externally visible promise needs legal sign-off before shipment.\n"
        ),
    )
    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="generic-approval.md",
        title="Launch Approval Notes",
        content=(
            "# Approval\n\n"
            "Approval notes before launch export review.\n"
        ),
    )

    hits = RetrievalService(repository).retrieve(
        "Need approval for public claims before launch.",
        domain="content-ops",
        top_k=3,
    )

    assert hits, "Expected at least one hit in the synonym diagnostic case."
    assert hits[0]["title"] == "Claims Sign-off Policy"


def test_retrieval_diagnostics_word_variant_normalization_is_now_stable(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="approval-guardrails.md",
        title="Approvals Guardrails",
        content=(
            "# Guardrails\n\n"
            "Reviewed packages need archived evidence before release.\n"
        ),
    )
    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="generic-approval-notes.md",
        title="Approval Notes",
        content=(
            "# Notes\n\n"
            "Approval approval launch review export approval.\n"
        ),
    )

    hits = RetrievalService(repository).retrieve(
        "Need approval guardrail before launch.",
        domain="content-ops",
        top_k=3,
    )

    assert hits, "Expected at least one hit in the word-variant diagnostic case."
    assert hits[0]["title"] == "Approvals Guardrails"
