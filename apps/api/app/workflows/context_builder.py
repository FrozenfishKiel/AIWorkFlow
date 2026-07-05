from __future__ import annotations

from typing import Any


class ContextBuilder:
    """Builds a constrained generation context from parsed input and retrieval hits.

    The current project does not yet have a real model prompt layer, but we
    still want one explicit place where context selection rules live. That keeps
    "what gets passed into generation" separate from retrieval and generation
    formatting, and gives us a stable surface for later prompt wiring.
    """

    GENERIC_PRODUCT_MATCH_TERMS = {
        "product",
        "category",
        "audience",
        "scenario",
        "scenarios",
        "feature",
        "features",
        "guide",
        "template",
        "商品",
        "产品",
        "资料",
        "模板",
        "内容",
        "文案",
        "任务",
        "目标",
        "卖点",
        "核心",
        "核心卖",
        "核心卖点",
        "场景",
        "使用",
        "使用场",
        "用场",
        "用场景",
        "用户",
        "人群",
        "活动",
        "平台",
        "品牌",
        "生成",
    }
    SPECIFIC_PRODUCT_SOURCE_TYPES = {
        "product_fact_card",
        "category_fact_card",
    }
    GENERIC_PRODUCT_SOURCE_TYPES = {
        "product_template",
        "brand_guide",
        "platform_guide",
        "history_reference",
        "high_performing_examples",
    }

    def build(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        deduped_hits: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, str]] = set()
        duplicate_hits_removed = 0

        for hit in retrieval_hits:
            signature = (str(hit["source_id"]), hit["snippet"].strip())
            if signature in seen_signatures:
                duplicate_hits_removed += 1
                continue
            seen_signatures.add(signature)
            deduped_hits.append(hit)

        if parsed_input["source_kind"] == "product_request":
            selected_hits = self._select_product_hits(deduped_hits)
            weak_retrieval = not any(self._is_specific_product_hit(hit) for hit in selected_hits)
            sections = [
                "product_brief",
                "task_description",
                "retrieval_evidence",
                "value_point_constraints",
            ]
            return {
                "sections": sections,
                "input_summary": understanding["summary"],
                "selected_hits": selected_hits,
                "duplicate_hits_removed": duplicate_hits_removed,
                "manual_checks": [],
                "quality_flags": parsed_input["input_quality"]["quality_flags"],
                "retrieval_quality": {
                    "candidate_hit_count": len(retrieval_hits),
                    "selected_hit_count": len(selected_hits),
                    "weak_retrieval": weak_retrieval,
                    "duplicate_hits_removed": duplicate_hits_removed,
                },
            }

        selected_hits = deduped_hits[:3]

        sections = [
            "task_goal",
            "input_summary",
            "retrieval_evidence",
            "risk_and_uncertainty_flags",
        ]
        return {
            "sections": sections,
            "input_summary": understanding["summary"],
            "selected_hits": selected_hits,
            "duplicate_hits_removed": duplicate_hits_removed,
            "manual_checks": understanding["uncertain_items"],
            "quality_flags": parsed_input["input_quality"]["quality_flags"],
            "retrieval_quality": {
                "candidate_hit_count": len(retrieval_hits),
                "selected_hit_count": len(selected_hits),
                "weak_retrieval": len(selected_hits) == 0,
                "duplicate_hits_removed": duplicate_hits_removed,
            },
        }

    def _select_product_hits(self, retrieval_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        specific_hits = [hit for hit in retrieval_hits if self._is_specific_product_hit(hit)]
        support_hits = [hit for hit in retrieval_hits if not self._is_specific_product_hit(hit)]
        return [*specific_hits, *support_hits][:3]

    def _is_specific_product_hit(self, hit: dict[str, Any]) -> bool:
        source_type = str(hit.get("source_type") or "").strip()
        if source_type in self.SPECIFIC_PRODUCT_SOURCE_TYPES:
            return True
        if source_type in self.GENERIC_PRODUCT_SOURCE_TYPES:
            return False

        title = str(hit.get("title") or "").strip()
        if "事实卡" in title:
            return True

        matched_phrases = [
            str(item).strip()
            for item in hit.get("matched_phrases", [])
            if str(item).strip()
        ]
        if any(not self._is_generic_product_match(item) for item in matched_phrases):
            return True

        matched_terms = [
            str(item).strip()
            for item in hit.get("matched_terms", [])
            if str(item).strip()
        ]
        return any(not self._is_generic_product_match(item) for item in matched_terms)

    def _is_generic_product_match(self, text: str) -> bool:
        normalized = str(text).strip()
        if not normalized:
            return True
        return normalized in self.GENERIC_PRODUCT_MATCH_TERMS
