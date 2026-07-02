from __future__ import annotations

from typing import Any


class ContextBuilder:
    """Builds a constrained generation context from parsed input and retrieval hits.

    The current project does not yet have a real model prompt layer, but we
    still want one explicit place where context selection rules live. That keeps
    "what gets passed into generation" separate from retrieval and generation
    formatting, and gives us a stable surface for later prompt wiring.
    """

    def build(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        selected_hits: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, str]] = set()
        duplicate_hits_removed = 0

        for hit in retrieval_hits:
            signature = (hit["source_id"], hit["snippet"].strip())
            if signature in seen_signatures:
                duplicate_hits_removed += 1
                continue
            seen_signatures.add(signature)
            selected_hits.append(hit)
            if len(selected_hits) >= 3:
                break

        if parsed_input["source_kind"] == "product_request":
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
            }

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
        }
