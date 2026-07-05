from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.default_ecommerce_knowledge import ensure_default_ecommerce_knowledge
from app.services.knowledge_index_service import KnowledgeIndexService


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
        "商品资料模板",
        "黑咖啡浓缩液事实卡",
        "便携挂脖小风扇事实卡",
        "洁面个护清洁事实卡",
        "轻食零食事实卡",
        "宠物清洁事实卡",
    }
    assert all(document.status == "indexed" for document in documents)
    assert len(documents) == len({document.source_path for document in documents})


def test_default_ecommerce_knowledge_seed_reindexes_when_default_source_changes(
    session: Session,
    tmp_path,
    monkeypatch,
) -> None:
    source_root = tmp_path / "knowledge-base" / "02-curated-notes" / "ecommerce"
    source_root.mkdir(parents=True)
    source_file = source_root / "品牌语气规范.md"
    source_file.write_text(
        "# 品牌语气规范\n\n"
        "## 基础要求\n\n"
        "- 语气要自然可信。\n"
        "- 不要夸大承诺。\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.services.default_ecommerce_knowledge.get_settings",
        lambda: SimpleNamespace(repo_root=tmp_path),
    )
    monkeypatch.setattr(
        "app.services.default_ecommerce_knowledge.DEFAULT_ECOMMERCE_DOCUMENTS",
        (
            {
                "title": "品牌语气规范",
                "filename": "品牌语气规范.md",
                "source_type": "brand_guide",
                "domain": "ecommerce",
            },
        ),
    )

    repository = KnowledgeRepository(session)
    ensure_default_ecommerce_knowledge(session)

    source_file.write_text(
        "# 品牌语气规范\n\n"
        "## 基础要求\n\n"
        "- 语气要自然可信。\n"
        "- 不要夸大承诺。\n\n"
        "## 售后口径\n\n"
        "- 售后时不要承诺极速达。\n",
        encoding="utf-8",
    )

    ensure_default_ecommerce_knowledge(session)

    document = repository.list_documents()[0]
    chunks = repository.list_chunks_for_document(document.id)

    assert any("售后时不要承诺极速达" in chunk.content for chunk in chunks)


def test_default_ecommerce_knowledge_seed_reindexes_when_stored_chunks_are_stale(
    session: Session,
    tmp_path,
    monkeypatch,
) -> None:
    source_root = tmp_path / "knowledge-base" / "02-curated-notes" / "ecommerce"
    source_root.mkdir(parents=True)
    source_file = source_root / "平台文案差异.md"
    source_text = (
        "# 平台文案差异\n\n"
        "## 淘宝 / 京东\n\n"
        "- 先讲核心卖点。\n"
        "- 再补规格参数。\n\n"
        "## 小红书\n\n"
        "- 先给用户场景。\n"
        "- 再补真实体验。\n"
    )
    source_file.write_text(source_text, encoding="utf-8")

    monkeypatch.setattr(
        "app.services.default_ecommerce_knowledge.get_settings",
        lambda: SimpleNamespace(repo_root=tmp_path),
    )
    monkeypatch.setattr(
        "app.services.default_ecommerce_knowledge.DEFAULT_ECOMMERCE_DOCUMENTS",
        (
            {
                "title": "平台文案差异",
                "filename": "平台文案差异.md",
                "source_type": "platform_guide",
                "domain": "ecommerce",
            },
        ),
    )

    repository = KnowledgeRepository(session)
    ensure_default_ecommerce_knowledge(session)
    document = repository.list_documents()[0]

    repository.replace_chunks(document=document, contents=[source_text.replace("\n", " ").strip()])
    repository.set_document_status(document=document, status="indexed", chunk_count=1, error_message=None)

    ensure_default_ecommerce_knowledge(session)

    expected_chunks = list(KnowledgeIndexService(repository)._chunk_text(source_text))
    actual_chunks = [chunk.content for chunk in repository.list_chunks_for_document(document.id)]

    assert len(actual_chunks) == len(expected_chunks)
    assert actual_chunks == expected_chunks


def test_default_ecommerce_knowledge_seed_does_not_rebuild_chunk_profiles_when_chunks_are_current(
    session: Session,
    tmp_path,
    monkeypatch,
) -> None:
    source_root = tmp_path / "knowledge-base" / "02-curated-notes" / "ecommerce"
    source_root.mkdir(parents=True)
    source_file = source_root / "品牌语气规范.md"
    source_file.write_text(
        "# 品牌语气规范\n\n"
        "## 基础要求\n\n"
        "- 语气要自然可信。\n"
        "- 不要夸大承诺。\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.services.default_ecommerce_knowledge.get_settings",
        lambda: SimpleNamespace(repo_root=tmp_path),
    )
    monkeypatch.setattr(
        "app.services.default_ecommerce_knowledge.DEFAULT_ECOMMERCE_DOCUMENTS",
        (
            {
                "title": "品牌语气规范",
                "filename": "品牌语气规范.md",
                "source_type": "brand_guide",
                "domain": "ecommerce",
            },
        ),
    )

    ensure_default_ecommerce_knowledge(session)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("build_chunk_records_from_path should not run for already indexed default docs")

    monkeypatch.setattr(
        KnowledgeIndexService,
        "build_chunk_records_from_path",
        fail_if_called,
    )

    ensure_default_ecommerce_knowledge(session)
