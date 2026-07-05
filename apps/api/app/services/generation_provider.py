from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


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


class ProductUnderstandingPayload(BaseModel):
    """Structured understanding contract for the product-content main chain."""

    summary: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    use_scenarios: list[str] = Field(default_factory=list)
    primary_value_points: list[str] = Field(default_factory=list)


class ProductWorkflowPayload(BaseModel):
    """Structured output contract for the product-content main chain."""

    selling_points_copy: list[str] = Field(default_factory=list)
    detail_page_copy: str = ""
    social_seed_copy: str = ""
    risk_notes: list[str] = Field(default_factory=list)
    applied_guidelines: list[str] = Field(default_factory=list)


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
                    "You are an ecommerce product analysis engine. "
                    "Return valid JSON only. Do not wrap the response in markdown. "
                    "Use the exact JSON keys: summary, target_audience, use_scenarios, primary_value_points. "
                    "use_scenarios and primary_value_points must be arrays of strings. "
                    "Write all values in Simplified Chinese. "
                    "Ground every field only in the provided product facts and task description. "
                    "Do not invent missing specifications, categories, audiences, scenarios, promotions, ingredients, materials, or claims. "
                    "If information is weak, keep the wording conservative and only restate what is actually present."
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
            normalized_target_audience = self._coerce_text_block(normalized_payload.get("target_audience"))
            normalized_payload["target_audience"] = (
                normalized_target_audience
                or str(parsed_input["product_payload"].get("target_audience") or "").strip()
                or "未明确目标人群"
            )
            return ProductUnderstandingPayload.model_validate(normalized_payload).model_dump()

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
                    "detail_page_copy and social_seed_copy must be plain strings. "
                    "Write all copy in Simplified Chinese. "
                    "Use product facts as the only source of factual claims. "
                    "Do not invent product facts, specifications, ingredients, materials, prices, audiences, scenes, promotions, or benefits that are not in the input. "
                    "Never use placeholder facts or guessed specifics such as 'XX克', '某成分', '某材质', '待补充', or similar stand-ins. "
                    "If an exact number or attribute is missing, omit that sentence instead of guessing. "
                    "Retrieval hits are constraints and writing guidance, not substitutes for missing product facts. "
                    "At least two selling points must directly reuse or clearly restate the provided core_selling_points. "
                    "Prefer core_selling_points and use_scenarios over generic specifications or price. "
                    "The detail_page_copy must mention the product name and must cover at least two concrete product facts from core_selling_points, target_audience, or use_scenarios. "
                    "The social_seed_copy must mention at least one use_scenario and one core_selling_point, and must not focus mainly on price or generic value-for-money language unless the task explicitly asks for that. "
                    "If retrieval_quality.weak_retrieval is true or the product info is incomplete, keep the copy conservative and say less rather than hallucinating. "
                    "Do not switch to English unless the input product itself requires it."
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
            return ProductWorkflowPayload.model_validate(normalized_payload).model_dump()

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
        return self._load_structured_json(content, schema_prompt=system_prompt)

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

    def _load_structured_json(
        self,
        content: str,
        *,
        schema_prompt: str,
    ) -> dict[str, Any]:
        last_error: json.JSONDecodeError | None = None
        for candidate in self._iter_json_candidates(content):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc

        repaired_content = self._repair_structured_content(
            schema_prompt=schema_prompt,
            malformed_content=content,
        )
        for candidate in self._iter_json_candidates(repaired_content):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise ValueError("DeepSeek returned empty structured content after repair.")

    def _repair_structured_content(
        self,
        *,
        schema_prompt: str,
        malformed_content: str,
    ) -> str:
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
                        "content": (
                            "You repair malformed JSON produced by another model. "
                            "Return valid JSON only. Do not add markdown, explanation, or extra keys. "
                            "Preserve the original language and follow the provided schema instructions exactly."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "schema_instructions": schema_prompt,
                                "malformed_content": self._truncate_text(malformed_content, 12000),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        return self._extract_message_content(payload)

    def _iter_json_candidates(self, content: str) -> list[str]:
        stripped = content.strip()
        if not stripped:
            return []

        candidates: list[str] = [stripped]
        fenced = self._strip_markdown_fence(stripped)
        if fenced and fenced not in candidates:
            candidates.append(fenced)

        for candidate in list(candidates):
            extracted = self._extract_json_object(candidate)
            if extracted and extracted not in candidates:
                candidates.append(extracted)

        return candidates

    def _strip_markdown_fence(self, content: str) -> str:
        stripped = content.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        return stripped

    def _extract_json_object(self, content: str) -> str | None:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return content[start : end + 1].strip()

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped


def build_task_generation_provider(
    settings: Settings | None = None,
    *,
    client: httpx.Client | None = None,
) -> TaskGenerationProvider:
    """Build the active generation provider from runtime settings."""

    resolved_settings = settings or get_settings()
    mode = resolved_settings.task_generation_provider.lower().strip()
    if mode not in {"auto", "deepseek"}:
        raise ValueError(
            f"Unsupported TASK_GENERATION_PROVIDER: {resolved_settings.task_generation_provider}. "
            "Only 'deepseek' is supported in the formal chain."
        )
    if not resolved_settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is required because the formal chain no longer supports deterministic fallback.")
    return DeepSeekTaskGenerationProvider(
        api_key=resolved_settings.deepseek_api_key,
        model=resolved_settings.deepseek_model,
        base_url=resolved_settings.deepseek_api_base_url,
        timeout_seconds=resolved_settings.deepseek_timeout_seconds,
        client=client,
    )
