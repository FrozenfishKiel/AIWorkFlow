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
    assert "launch review checklist" in hits[0]["reason"].lower()


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


def test_retrieval_diagnostics_semantic_synonyms_are_now_stable(
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
    assert "approval" in hits[0]["reason"].lower() or "public" in hits[0]["reason"].lower()


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


def test_retrieval_diagnostics_chinese_ecommerce_query_is_explainable(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="xiaohongshu-guide.md",
        title="小红书种草表达",
        content=(
            "# 小红书\n\n"
            "更适合从真实体验和场景感切入，避免直接堆硬广卖点。\n"
        ),
        domain="ecommerce",
    )
    _index_document(
        repository,
        tmp_path=tmp_path,
        file_name="brand-guide.md",
        title="品牌语气规范",
        content=(
            "# 品牌\n\n"
            "避免绝对化承诺，优先自然可靠的表达。\n"
        ),
        domain="ecommerce",
    )

    hits = RetrievalService(repository).retrieve(
        "想写夏季通勤补涂防晒的种草文案，重点是真实使用感，不要太广告。",
        domain="ecommerce",
        top_k=3,
    )

    assert hits, "Expected Chinese ecommerce retrieval to return explainable evidence."
    assert hits[0]["title"] == "小红书种草表达"
    assert "真实体验" in hits[0]["reason"]
    assert "score" not in hits[0]["reason"].lower()
