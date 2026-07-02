from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings


class ModelUnderstandingPayload(BaseModel):
    """Model-facing understanding payload without parser-owned quality metadata."""

    summary: str = Field(min_length=1)
    audience: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)
    uncertain_items: list[str] = Field(default_factory=list)


class ModelWorkflowPayload(BaseModel):
    """Model-facing workflow payload before the pipeline enriches traceability."""

    draft: str = Field(min_length=1)
    review_notes: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    manual_checks: list[str] = Field(default_factory=list)


class TaskGenerationProvider(Protocol):
    """Stable interface used by the task pipeline regardless of model vendor."""

    provider_name: str

    def build_understanding(self, parsed_input: dict[str, Any]) -> dict[str, Any]:
        """Return the structured understanding core for the current parsed input."""

    def build_workflow(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        generation_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the structured workflow core before traceability enrichment."""


class DeterministicTaskGenerationProvider:
    """Local fallback provider that preserves the old placeholder behavior."""

    provider_name = "deterministic-fallback"

    def build_understanding(self, parsed_input: dict[str, Any]) -> dict[str, Any]:
        if parsed_input["source_kind"] == "product_request":
            product_payload = parsed_input["product_payload"]
            name = str(product_payload.get("name") or "商品")
            target_audience = str(product_payload.get("target_audience") or "目标用户")
            scenarios = [str(item) for item in product_payload.get("use_scenarios", [])]
            selling_points = [str(item) for item in product_payload.get("core_selling_points", [])]
            return {
                "summary": (
                    f"{name} 面向 {target_audience}，本次应重点突出 "
                    f"{'、'.join(selling_points[:3]) or '核心卖点'}。"
                ),
                "target_audience": target_audience,
                "use_scenarios": scenarios,
                "primary_value_points": selling_points[:3],
            }

        parsed_text = str(parsed_input["parsed_text"])
        snippet = parsed_text[:80].strip() or "No content provided."
        payload = ModelUnderstandingPayload(
            summary=f"Structured summary for: {snippet}",
            audience=["content-ops", "brand"],
            key_points=[
                "The task requires structured understanding before generation.",
                "References should remain visible in the persisted record.",
                "Results should remain exportable without synchronous approval.",
            ],
            risk_points=["Claims still require post-run verification against cited evidence."],
            uncertain_items=["Final business angle may still need operator confirmation."],
        )
        return payload.model_dump()

    def build_workflow(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        generation_context: dict[str, Any],
    ) -> dict[str, Any]:
        if parsed_input["source_kind"] == "product_request":
            product_payload = parsed_input["product_payload"]
            name = str(product_payload.get("name") or "商品")
            selling_points = [str(item) for item in product_payload.get("core_selling_points", [])]
            guideline_titles = [str(hit["title"]) for hit in retrieval_hits]
            first_line = (
                f"{name}{selling_points[0]}，更适合{understanding.get('target_audience') or '目标用户'}日常使用。"
                if selling_points
                else f"{name}围绕真实使用场景整理了更清晰的卖点表达。"
            )
            return {
                "selling_points_copy": [
                    first_line,
                    f"围绕{'、'.join(understanding.get('use_scenarios', [])[:2]) or '日常场景'}组织信息，更方便运营继续改写。"
                ],
                "detail_page_copy": (
                    f"{name}这次主打{'、'.join(understanding.get('primary_value_points', [])[:3]) or '核心卖点'}，"
                    f"适合{'、'.join(understanding.get('use_scenarios', [])[:2]) or '日常使用'}场景，"
                    "详情页建议先讲核心体验，再补充规格与活动信息。"
                ),
                "social_seed_copy": (
                    f"{name}这版种草文案先强调真实体验和使用场景，"
                    f"更适合面向{understanding.get('target_audience') or '目标用户'}继续打磨。"
                ),
                "risk_notes": ["避免使用绝对化功效承诺，保持真实体验表达。"],
                "applied_guidelines": guideline_titles,
            }

        source_ids = ", ".join(hit["source_id"] for hit in retrieval_hits)
        payload = ModelWorkflowPayload(
            draft=(
                "Draft workflow result based on the structured understanding and visible retrieval hits. "
                f"Primary audience: {', '.join(understanding['audience'])}."
            ),
            review_notes=[
                "Confirm the final business angle before external use.",
                (
                    f"Verify the cited sources: {source_ids}."
                    if retrieval_hits
                    else "No indexed knowledge hits were available for this task yet."
                ),
            ],
            open_questions=[
                "Does the generated angle match the brand constraint?",
                "Are any claims missing manual confirmation?",
            ],
            manual_checks=[
                "Confirm the final business angle before external use.",
                "Verify every externally visible claim against the cited evidence.",
            ],
        )
        return payload.model_dump()


class DeepSeekTaskGenerationProvider:
    """DeepSeek-backed provider for real understanding and workflow generation."""

    provider_name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 45.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )

    def build_understanding(self, parsed_input: dict[str, Any]) -> dict[str, Any]:
        if parsed_input["source_kind"] == "product_request":
            response_payload = self._request_json_completion(
                system_prompt=(
                    "You are an ecommerce product content strategist. "
                    "Return valid JSON only. Do not wrap the response in markdown. "
                    "Use the exact JSON keys: summary, target_audience, use_scenarios, primary_value_points. "
                    "use_scenarios and primary_value_points must be arrays of strings."
                ),
                user_payload={
                    "task": "build_product_brief",
                    "product": parsed_input["product_payload"],
                    "task_description": parsed_input["task_description"],
                },
            )
            normalized_payload = self._normalize_list_fields(
                response_payload,
                fields=("use_scenarios", "primary_value_points"),
            )
            normalized_payload["summary"] = self._coerce_text_block(normalized_payload.get("summary"))
            normalized_payload["target_audience"] = self._coerce_text_block(
                normalized_payload.get("target_audience")
            )
            return normalized_payload

        response_payload = self._request_json_completion(
            system_prompt=(
                "You are an AI content-ops analysis engine. "
                "Return valid JSON only. Do not wrap the response in markdown. "
                "Use the exact JSON keys: summary, audience, key_points, risk_points, uncertain_items. "
                "The four *_points/audience/items fields must be JSON arrays of strings, not a single string."
            ),
            user_payload={
                "task": "build_understanding",
                "source_kind": parsed_input["source_kind"],
                "parsed_text": self._truncate_text(str(parsed_input["parsed_text"]), 12000),
                "input_quality": parsed_input["input_quality"],
            },
        )
        normalized_payload = self._normalize_list_fields(
            response_payload,
            fields=("audience", "key_points", "risk_points", "uncertain_items"),
        )
        return ModelUnderstandingPayload.model_validate(normalized_payload).model_dump()

    def build_workflow(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        generation_context: dict[str, Any],
    ) -> dict[str, Any]:
        if parsed_input["source_kind"] == "product_request":
            response_payload = self._request_json_completion(
                system_prompt=(
                    "You are an ecommerce copywriting assistant. "
                    "Return valid JSON only. Do not wrap the response in markdown. "
                    "Use the exact JSON keys: selling_points_copy, detail_page_copy, social_seed_copy, risk_notes, applied_guidelines. "
                    "selling_points_copy, risk_notes, and applied_guidelines must be arrays of strings. "
                    "detail_page_copy and social_seed_copy must be plain strings."
                ),
                user_payload={
                    "task": "build_product_content",
                    "product": parsed_input["product_payload"],
                    "task_description": parsed_input["task_description"],
                    "product_brief": understanding,
                    "retrieval_hits": retrieval_hits,
                    "generation_context": generation_context,
                },
            )
            normalized_payload = self._normalize_list_fields(
                response_payload,
                fields=("selling_points_copy", "risk_notes", "applied_guidelines"),
            )
            normalized_payload["detail_page_copy"] = self._coerce_text_block(
                normalized_payload.get("detail_page_copy")
            )
            normalized_payload["social_seed_copy"] = self._coerce_text_block(
                normalized_payload.get("social_seed_copy")
            )
            return normalized_payload

        response_payload = self._request_json_completion(
            system_prompt=(
                "You are an AI content-ops workflow planner. "
                "Return valid JSON only. Do not wrap the response in markdown. "
                "Use the exact JSON keys: draft, review_notes, open_questions, manual_checks. "
                "The review_notes, open_questions, and manual_checks fields must be JSON arrays of strings. "
                "Ground the draft in the provided evidence and keep reviewer-visible uncertainty explicit."
            ),
            user_payload={
                "task": "build_workflow",
                "parsed_text": self._truncate_text(str(parsed_input["parsed_text"]), 12000),
                "understanding": understanding,
                "retrieval_hits": retrieval_hits,
                "generation_context": generation_context,
            },
        )
        normalized_payload = self._normalize_list_fields(
            response_payload,
            fields=("review_notes", "open_questions", "manual_checks"),
        )
        normalized_payload["draft"] = self._coerce_text_block(normalized_payload.get("draft"))
        return ModelWorkflowPayload.model_validate(normalized_payload).model_dump()

    def _request_json_completion(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.post(
            "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = self._extract_message_content(payload)
        if not content.strip():
            raise ValueError("DeepSeek returned empty content for structured generation.")
        return json.loads(content)

    def _extract_message_content(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("DeepSeek response did not contain any choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict)
            )
        return ""

    def _truncate_text(self, text: str, max_chars: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= max_chars:
            return normalized
        return normalized[:max_chars] + "...[truncated]"

    def _normalize_list_fields(
        self,
        payload: dict[str, Any],
        *,
        fields: tuple[str, ...],
    ) -> dict[str, Any]:
        """Coerce common model drift into the strict schema expected downstream."""

        normalized = dict(payload)
        for field_name in fields:
            normalized[field_name] = self._coerce_string_list(normalized.get(field_name))
        return normalized

    def _coerce_string_list(self, value: Any) -> list[str]:
        """Accept either one string or a list-like payload and return clean strings."""

        if value is None:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        if isinstance(value, list):
            coerced: list[str] = []
            for item in value:
                cleaned = str(item).strip()
                if cleaned:
                    coerced.append(cleaned)
            return coerced
        cleaned = str(value).strip()
        return [cleaned] if cleaned else []

    def _coerce_text_block(self, value: Any) -> str:
        """Normalize model text fields that sometimes come back as bullet arrays."""

        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = [str(item).strip() for item in value if str(item).strip()]
            return "\n".join(parts)
        return str(value).strip()


def build_task_generation_provider(
    settings: Settings | None = None,
    *,
    client: httpx.Client | None = None,
) -> TaskGenerationProvider:
    """Build the active generation provider from runtime settings."""

    resolved_settings = settings or get_settings()
    mode = resolved_settings.task_generation_provider.lower().strip()

    if mode == "deepseek" or (mode == "auto" and resolved_settings.deepseek_api_key):
        if not resolved_settings.deepseek_api_key:
            raise ValueError(
                "TASK_GENERATION_PROVIDER is set to 'deepseek' but no DEEPSEEK_API_KEY is configured."
            )
        return DeepSeekTaskGenerationProvider(
            api_key=resolved_settings.deepseek_api_key,
            model=resolved_settings.deepseek_model,
            base_url=resolved_settings.deepseek_api_base_url,
            timeout_seconds=resolved_settings.deepseek_timeout_seconds,
            client=client,
        )

    return DeterministicTaskGenerationProvider()
