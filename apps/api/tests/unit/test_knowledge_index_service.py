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


def test_knowledge_index_service_splits_structured_sections_into_multiple_chunks(
    session: Session,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "platform-guide.md"
    source_file.write_text(
        "# 平台文案差异\n\n"
        "不同平台的内容重点不同。\n\n"
        "## 淘宝 / 京东\n\n"
        "- 先讲核心卖点。\n"
        "- 再补规格参数和活动信息。\n\n"
        "## 小红书\n\n"
        "- 更适合真实体验和场景感切入。\n"
        "- 不要一上来就是硬广口吻。\n",
        encoding="utf-8",
    )

    repository = KnowledgeRepository(session)
    document = repository.create_document(
        title="平台文案差异",
        source_path=str(source_file),
        source_type="platform_guide",
        domain="ecommerce",
    )

    service = KnowledgeIndexService(repository)
    indexed_document = service.index_document(document.id)
    chunks = repository.list_chunks_for_document(document.id)

    assert indexed_document.status == "indexed"
    assert indexed_document.chunk_count == len(chunks)
    assert indexed_document.chunk_count >= 3
    assert any("淘宝 / 京东" in chunk.content and "规格参数" in chunk.content for chunk in chunks)
    assert any("小红书" in chunk.content and "真实体验" in chunk.content for chunk in chunks)


def test_knowledge_index_service_splits_list_rules_into_atomic_chunks(
    session: Session,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "atomic-platform-guide.md"
    source_file.write_text(
        "# 平台规则\n\n"
        "## 禁用表达\n\n"
        "- 不要写最强。\n"
        "- 不要写百分百有效。\n\n"
        "## 详情页结构\n\n"
        "- 先讲核心卖点。\n"
        "- 再补规格参数。\n",
        encoding="utf-8",
    )

    repository = KnowledgeRepository(session)
    document = repository.create_document(
        title="平台规则",
        source_path=str(source_file),
        source_type="platform_rule",
        domain="ecommerce",
    )

    service = KnowledgeIndexService(repository)
    service.index_document(document.id)
    chunk_contents = [chunk.content for chunk in repository.list_chunks_for_document(document.id)]

    assert any("平台规则\n禁用表达" in chunk and "不要写最强" in chunk for chunk in chunk_contents)
    assert any("平台规则\n禁用表达" in chunk and "不要写百分百有效" in chunk for chunk in chunk_contents)
    assert any("平台规则\n详情页结构" in chunk and "先讲核心卖点" in chunk for chunk in chunk_contents)
    assert any("平台规则\n详情页结构" in chunk and "再补规格参数" in chunk for chunk in chunk_contents)
    assert not any("不要写最强" in chunk and "不要写百分百有效" in chunk for chunk in chunk_contents)
    assert not any("先讲核心卖点" in chunk and "再补规格参数" in chunk for chunk in chunk_contents)
