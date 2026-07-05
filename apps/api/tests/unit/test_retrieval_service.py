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
    assert "manual review" in hits[0]["reason"].lower()
    assert "score" not in hits[0]["reason"].lower()
    assert "vector" not in hits[0]["reason"].lower()


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
    assert "launch review checklist" in hits[0]["reason"].lower()


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
    assert "public claim" in hits[0]["reason"].lower()
    assert "score" not in hits[0]["reason"].lower()


def test_retrieval_service_handles_chinese_queries_with_readable_reasons(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    platform_file = tmp_path / "platform-guide.md"
    platform_file.write_text(
        "# 小红书表达\n\n"
        "更适合从真实体验、场景感和继续使用意愿切入，避免直接堆砌硬广卖点。\n",
        encoding="utf-8",
    )
    template_file = tmp_path / "product-template.md"
    template_file.write_text(
        "# 商品资料模板\n\n"
        "商品资料至少要有规格参数、目标人群和使用场景，缺失时优先保守表达。\n",
        encoding="utf-8",
    )

    platform_document = repository.create_document(
        title="小红书表达建议",
        source_path=str(platform_file),
        source_type="platform_guide",
        domain="ecommerce",
    )
    template_document = repository.create_document(
        title="商品资料模板",
        source_path=str(template_file),
        source_type="product_template",
        domain="ecommerce",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(platform_document.id)
    index_service.index_document(template_document.id)

    hits = RetrievalService(repository).retrieve(
        "想写夏季通勤补涂防晒的种草文案，重点突出真实使用感，不要太广告。",
        top_k=3,
        domain="ecommerce",
    )

    assert hits
    assert hits[0]["title"] == "小红书表达建议"
    assert "真实体验" in hits[0]["reason"]
    assert "score" not in hits[0]["reason"].lower()
    assert "vector" not in hits[0]["reason"].lower()


def test_retrieval_service_uses_profile_synonyms_and_constraints_for_ecommerce_ranking(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    lifestyle_file = tmp_path / "xiaohongshu-guide.md"
    lifestyle_file.write_text(
        "# 小红书表达\n\n"
        "防晒种草更适合从真实体验、场景感和继续使用意愿切入，避免硬广口吻。\n",
        encoding="utf-8",
    )
    ingredient_file = tmp_path / "ingredient-notes.md"
    ingredient_file.write_text(
        "# 成分说明\n\n"
        "这款防晒喷雾适合夏季通勤补涂，成分表与喷头参数如下。\n",
        encoding="utf-8",
    )

    lifestyle_document = repository.create_document(
        title="小红书种草表达",
        source_path=str(lifestyle_file),
        source_type="platform_guide",
        domain="ecommerce",
    )
    ingredient_document = repository.create_document(
        title="防晒成分说明",
        source_path=str(ingredient_file),
        source_type="product_notes",
        domain="ecommerce",
    )

    class FakeRetrievalProfileProvider:
        provider_name = "fake-ecommerce-profile"

        def build_chunk_profile(self, *, title: str, content: str, domain: str, source_type: str) -> dict[str, object]:
            if title == "小红书种草表达":
                return {
                    "retrieval_text": "真实体验 场景感 小红书 ecommerce platform_guide",
                    "keywords": ["真实体验", "场景感"],
                    "synonyms": ["种草", "使用感"],
                    "constraints": [domain, source_type, "小红书"],
                }
            return {
                "retrieval_text": "防晒喷雾 夏季通勤 补涂 ecommerce product_notes",
                "keywords": ["防晒喷雾", "夏季通勤", "补涂"],
                "synonyms": [],
                "constraints": [domain, source_type],
            }

        def build_query_profile(self, *, query_text: str, domain: str | None) -> dict[str, object]:
            return {
                "retrieval_text": "防晒喷雾",
                "keywords": ["防晒喷雾"],
                "synonyms": ["真实体验", "场景感", "使用感"],
                "constraints": [value for value in ["小红书", domain] if value],
            }

    class FlatEmbeddingService:
        def embed_text(self, text: str) -> list[float]:
            return [1.0, 0.0, 0.0]

    index_service = KnowledgeIndexService(
        repository,
        retrieval_profile_provider=FakeRetrievalProfileProvider(),
        embedding_service=FlatEmbeddingService(),
    )
    index_service.index_document(lifestyle_document.id)
    index_service.index_document(ingredient_document.id)

    hits = RetrievalService(
        repository,
        retrieval_profile_provider=FakeRetrievalProfileProvider(),
        embedding_service=FlatEmbeddingService(),
    ).retrieve(
        "需要一份更适合平台场景的表达参考。",
        top_k=3,
        domain="ecommerce",
    )

    assert hits
    assert hits[0]["title"] == "小红书种草表达"
    assert "真实体验" in hits[0]["reason"] or "场景感" in hits[0]["reason"]
    assert "小红书" in hits[0]["reason"]


def test_retrieval_service_returns_document_diverse_hits_for_product_queries(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    fact_file = tmp_path / "coffee-fact.md"
    fact_file.write_text(
        "# 黑咖啡浓缩液事实卡\n\n"
        "## 常见关键属性\n\n"
        "- 通勤携带方便。\n"
        "- 冷水也能快速冲开。\n\n"
        "## 用户高频关注点\n\n"
        "- 咖啡味够不够明显。\n",
        encoding="utf-8",
    )
    brand_file = tmp_path / "brand-guide.md"
    brand_file.write_text(
        "# 品牌语气规范\n\n"
        "种草文案更适合从真实使用感和生活场景切入。\n",
        encoding="utf-8",
    )

    fact_document = repository.create_document(
        title="黑咖啡浓缩液事实卡",
        source_path=str(fact_file),
        source_type="product_fact_card",
        domain="ecommerce",
    )
    brand_document = repository.create_document(
        title="品牌语气规范",
        source_path=str(brand_file),
        source_type="brand_guide",
        domain="ecommerce",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(fact_document.id)
    index_service.index_document(brand_document.id)

    hits = RetrievalService(repository).retrieve(
        "商品 黑咖啡浓缩液\n类目 冲调饮品\n核心卖点 便携提神 冷水即溶\n内容目标 小红书 种草 真实体验 使用感 场景感",
        top_k=4,
        domain="ecommerce",
    )

    assert hits
    assert hits[0]["title"] == "黑咖啡浓缩液事实卡"
    assert len(hits) == len({hit["source_id"] for hit in hits})
    assert {hit["title"] for hit in hits} >= {"黑咖啡浓缩液事实卡", "品牌语气规范"}


def test_retrieval_service_filters_irrelevant_fact_cards_from_product_queries(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    pet_file = tmp_path / "pet-clean.md"
    pet_file.write_text(
        "# 宠物清洁事实卡\n\n"
        "## 常见场景\n\n"
        "- 宠物家庭的日常除味与清洁。\n"
        "- 更适合围绕温和除味和家居环境表达。\n",
        encoding="utf-8",
    )
    fan_file = tmp_path / "fan-fact.md"
    fan_file.write_text(
        "# 便携挂脖小风扇事实卡\n\n"
        "## 常见场景\n\n"
        "- 通勤排队时解放双手。\n"
        "- 夏季外出随身降温。\n",
        encoding="utf-8",
    )
    template_file = tmp_path / "template.md"
    template_file.write_text(
        "# 商品资料模板\n\n"
        "商品资料至少要有规格参数、目标人群和使用场景，缺失时优先保守表达。\n",
        encoding="utf-8",
    )

    pet_document = repository.create_document(
        title="宠物清洁事实卡",
        source_path=str(pet_file),
        source_type="category_fact_card",
        domain="ecommerce",
    )
    fan_document = repository.create_document(
        title="便携挂脖小风扇事实卡",
        source_path=str(fan_file),
        source_type="product_fact_card",
        domain="ecommerce",
    )
    template_document = repository.create_document(
        title="商品资料模板",
        source_path=str(template_file),
        source_type="product_template",
        domain="ecommerce",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(pet_document.id)
    index_service.index_document(fan_document.id)
    index_service.index_document(template_document.id)

    hits = RetrievalService(repository).retrieve(
        "商品 宠物除味喷雾\n类目 宠物清洁\n核心卖点 日常除味\n内容目标 种草 保守表达",
        top_k=4,
        domain="ecommerce",
    )

    assert hits
    assert {hit["title"] for hit in hits} >= {"宠物清洁事实卡", "商品资料模板"}
    assert "便携挂脖小风扇事实卡" not in {hit["title"] for hit in hits}


def test_retrieval_service_boosts_aligned_fact_cards_over_generic_ecommerce_guides(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    fact_file = tmp_path / "pet-clean-fact.md"
    fact_file.write_text(
        "# 宠物清洁事实卡\n\n"
        "常见表达围绕去味、猫砂盆附近、沙发和居家异味场景展开。\n",
        encoding="utf-8",
    )
    template_file = tmp_path / "product-template.md"
    template_file.write_text(
        "# 商品资料模板\n\n"
        "商品资料至少应包含规格、卖点、人群和使用场景。\n",
        encoding="utf-8",
    )
    tone_file = tmp_path / "brand-tone.md"
    tone_file.write_text(
        "# 品牌语气规范\n\n"
        "优先真实体验，避免绝对化承诺。\n",
        encoding="utf-8",
    )

    fact_document = repository.create_document(
        title="宠物清洁事实卡",
        source_path=str(fact_file),
        source_type="category_fact_card",
        domain="ecommerce",
    )
    template_document = repository.create_document(
        title="商品资料模板",
        source_path=str(template_file),
        source_type="product_template",
        domain="ecommerce",
    )
    tone_document = repository.create_document(
        title="品牌语气规范",
        source_path=str(tone_file),
        source_type="brand_guide",
        domain="ecommerce",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(fact_document.id)
    index_service.index_document(template_document.id)
    index_service.index_document(tone_document.id)

    hits = RetrievalService(repository).retrieve(
        "商品 宠物除味喷雾\n类目 宠物清洁\n核心卖点 去味 日常家用\n使用场景 猫砂盆附近 沙发 空气异味",
        top_k=3,
        domain="ecommerce",
    )

    assert hits
    assert hits[0]["title"] == "宠物清洁事实卡"
    assert hits[0]["source_type"] == "category_fact_card"


def test_retrieval_service_does_not_keep_generic_cleaning_fact_cards_for_pet_queries(
    session: Session,
    tmp_path: Path,
) -> None:
    repository = KnowledgeRepository(session)

    pet_file = tmp_path / "pet-clean-fact.md"
    pet_file.write_text(
        "# 宠物清洁事实卡\n\n"
        "宠物清洁更适合围绕去味、猫砂盆附近和家居环境表达。\n",
        encoding="utf-8",
    )
    cleanser_file = tmp_path / "cleanser-fact.md"
    cleanser_file.write_text(
        "# 洁面个护清洁事实卡\n\n"
        "洁面类更适合围绕泡沫感、洗后肤感和是否紧绷表达。\n",
        encoding="utf-8",
    )
    template_file = tmp_path / "template.md"
    template_file.write_text(
        "# 商品资料模板\n\n"
        "商品资料至少要有规格参数、目标人群和使用场景。\n",
        encoding="utf-8",
    )

    pet_document = repository.create_document(
        title="宠物清洁事实卡",
        source_path=str(pet_file),
        source_type="category_fact_card",
        domain="ecommerce",
    )
    cleanser_document = repository.create_document(
        title="洁面个护清洁事实卡",
        source_path=str(cleanser_file),
        source_type="category_fact_card",
        domain="ecommerce",
    )
    template_document = repository.create_document(
        title="商品资料模板",
        source_path=str(template_file),
        source_type="product_template",
        domain="ecommerce",
    )

    index_service = KnowledgeIndexService(repository)
    index_service.index_document(pet_document.id)
    index_service.index_document(cleanser_document.id)
    index_service.index_document(template_document.id)

    hits = RetrievalService(repository).retrieve(
        "商品 宠物除味喷雾\n类目 宠物清洁\n核心卖点 日常除味\n内容目标 种草 保守表达",
        top_k=4,
        domain="ecommerce",
    )

    assert hits
    assert "宠物清洁事实卡" in {hit["title"] for hit in hits}
    assert "洁面个护清洁事实卡" not in {hit["title"] for hit in hits}
