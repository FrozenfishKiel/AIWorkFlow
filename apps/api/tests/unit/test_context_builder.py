from app.workflows.context_builder import ContextBuilder


def _parsed_input() -> dict[str, object]:
    return {
        "source_kind": "product_request",
        "input_quality": {"quality_flags": []},
    }


def _understanding() -> dict[str, object]:
    return {
        "summary": "一款面向养宠家庭的宠物除味喷雾。",
    }


def test_context_builder_keeps_generic_guides_but_marks_product_retrieval_weak_without_fact_hits() -> None:
    context = ContextBuilder().build(
        parsed_input=_parsed_input(),
        understanding=_understanding(),
        retrieval_hits=[
            {
                "source_id": "guide-1",
                "title": "商品资料模板",
                "snippet": "商品资料至少要有规格、卖点和使用场景。",
                "reason": "命中商品资料模板。",
                "source_type": "product_template",
            },
            {
                "source_id": "guide-2",
                "title": "品牌语气规范",
                "snippet": "优先真实体验，避免绝对化承诺。",
                "reason": "命中品牌语气规范。",
                "source_type": "brand_guide",
            },
        ],
    )

    assert [hit["title"] for hit in context["selected_hits"]] == ["商品资料模板", "品牌语气规范"]
    assert context["retrieval_quality"]["selected_hit_count"] == 2
    assert context["retrieval_quality"]["weak_retrieval"] is True


def test_context_builder_prioritizes_fact_cards_over_generic_guides_for_product_requests() -> None:
    context = ContextBuilder().build(
        parsed_input=_parsed_input(),
        understanding=_understanding(),
        retrieval_hits=[
            {
                "source_id": "guide-1",
                "title": "商品资料模板",
                "snippet": "商品资料至少要有规格、卖点和使用场景。",
                "reason": "命中商品资料模板。",
                "source_type": "product_template",
            },
            {
                "source_id": "fact-1",
                "title": "宠物清洁事实卡",
                "snippet": "常见表达围绕去味、居家环境、猫砂盆附近等场景。",
                "reason": "命中宠物清洁事实卡。",
                "source_type": "category_fact_card",
            },
            {
                "source_id": "guide-2",
                "title": "平台文案差异",
                "snippet": "详情页适合先讲核心卖点，再补规格与活动信息。",
                "reason": "命中平台文案差异。",
                "source_type": "platform_guide",
            },
        ],
    )

    assert [hit["title"] for hit in context["selected_hits"]] == [
        "宠物清洁事实卡",
        "商品资料模板",
        "平台文案差异",
    ]
    assert context["retrieval_quality"]["selected_hit_count"] == 3
    assert context["retrieval_quality"]["weak_retrieval"] is False


def test_context_builder_keeps_weak_retrieval_true_when_generic_guides_carry_only_meta_match_terms() -> None:
    context = ContextBuilder().build(
        parsed_input=_parsed_input(),
        understanding=_understanding(),
        retrieval_hits=[
            {
                "source_id": "guide-1",
                "title": "商品资料模板",
                "snippet": "商品资料模板 核心卖点",
                "reason": "命中商品资料模板。",
                "source_type": "product_template",
                "matched_terms": ["商品", "核心卖点", "场景"],
                "matched_phrases": ["核心 心卖 卖点"],
            },
            {
                "source_id": "guide-2",
                "title": "历史优稿参考",
                "snippet": "再补充适用人群和使用场景。",
                "reason": "命中历史优稿参考。",
                "source_type": "high_performing_examples",
                "matched_terms": ["人群", "用户", "用场景"],
                "matched_phrases": ["使用 用场 场景"],
            },
            {
                "source_id": "guide-3",
                "title": "平台文案差异",
                "snippet": "更适合先讲核心卖点，再补规格参数。",
                "reason": "命中平台文案差异。",
                "source_type": "platform_guide",
                "matched_terms": ["核心卖", "活动"],
                "matched_phrases": ["核心 心卖"],
            },
        ],
    )

    assert [hit["title"] for hit in context["selected_hits"]] == [
        "商品资料模板",
        "历史优稿参考",
        "平台文案差异",
    ]
    assert context["retrieval_quality"]["selected_hit_count"] == 3
    assert context["retrieval_quality"]["weak_retrieval"] is True
