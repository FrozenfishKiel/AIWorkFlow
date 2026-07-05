from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff\-]{2,}")
TOKEN_SYNONYMS = {
    "sign-off": "approval",
    "signoffs": "approval",
    "signoff": "approval",
    "externally": "public",
    "external": "public",
    "visible": "public",
}
QUERY_NOISE_TERMS = {
    "商品",
    "产品",
    "任务",
    "描述",
    "内容",
    "文案",
    "生成",
    "输出",
    "需要",
    "想写",
    "帮我写",
    "一版",
    "突出",
    "当前",
}
PHRASE_SYNONYM_MAP = {
    "approval": ["sign-off"],
    "public": ["externally visible"],
    "externally visible": ["public"],
    "小红书": ["种草", "真实体验", "场景感"],
    "种草": ["真实体验", "场景感", "使用感"],
    "使用感": ["真实体验", "场景感"],
    "详情页": ["卖点拆解", "参数说明", "购买理由"],
    "卖点": ["核心优势", "购买理由"],
    "通勤": ["日常出行"],
    "夏季通勤": ["日常通勤"],
    "补涂": ["随身补用"],
    "防晒": ["隔离紫外线"],
}
CONSTRAINT_PHRASES = (
    "小红书",
    "种草",
    "详情页",
    "卖点",
    "直播",
    "短视频",
)
logger = logging.getLogger(__name__)


class RetrievalProfilePayload(BaseModel):
    """Compact retrieval profile used to vectorize both chunks and queries."""

    retrieval_text: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class RetrievalProfileProvider(Protocol):
    """Stable provider interface for semantic retrieval normalization."""

    provider_name: str

    def build_chunk_profile(
        self,
        *,
        title: str,
        content: str,
        domain: str,
        source_type: str,
    ) -> dict[str, Any]:
        """Build a retrieval profile for one indexed knowledge chunk."""

    def build_query_profile(
        self,
        *,
        query_text: str,
        domain: str | None,
    ) -> dict[str, Any]:
        """Build a retrieval profile for one incoming retrieval query."""

class DeepSeekRetrievalProfileProvider:
    """DeepSeek-backed semantic profile builder for query/chunk normalization."""

    provider_name = "deepseek-retrieval-profile"

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

    def build_chunk_profile(
        self,
        *,
        title: str,
        content: str,
        domain: str,
        source_type: str,
    ) -> dict[str, Any]:
        response_payload = self._request_json_completion(
            system_prompt=(
                "You build retrieval profiles for a scoped business knowledge base used by an ecommerce content-generation system. "
                "Return valid JSON only with the exact keys: retrieval_text, keywords, synonyms, constraints. "
                "retrieval_text must be one compact search-oriented text block that preserves meaning, expands obvious business synonyms, "
                "and keeps domain constraints visible. The list fields must be arrays of strings."
            ),
            user_payload={
                "task": "build_chunk_retrieval_profile",
                "title": title,
                "domain": domain,
                "source_type": source_type,
                "content": self._truncate_text(content, 8000),
            },
        )
        normalized_payload = self._normalize_payload(response_payload)
        return RetrievalProfilePayload.model_validate(normalized_payload).model_dump()

    def build_query_profile(
        self,
        *,
        query_text: str,
        domain: str | None,
    ) -> dict[str, Any]:
        response_payload = self._request_json_completion(
            system_prompt=(
                "You normalize user retrieval queries for a scoped business knowledge base used by an ecommerce content-generation system. "
                "Return valid JSON only with the exact keys: retrieval_text, keywords, synonyms, constraints. "
                "retrieval_text must restate the search intent using stable business language so semantically similar chunks can still match. "
                "The list fields must be arrays of strings."
            ),
            user_payload={
                "task": "build_query_retrieval_profile",
                "domain": domain,
                "query_text": self._truncate_text(query_text, 4000),
            },
        )
        normalized_payload = self._normalize_payload(response_payload)
        return RetrievalProfilePayload.model_validate(normalized_payload).model_dump()

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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = self._extract_message_content(payload)
        if not content.strip():
            raise ValueError("DeepSeek returned empty content for retrieval profile generation.")
        return self._load_structured_json(content, schema_prompt=system_prompt)

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["retrieval_text"] = self._coerce_text_block(normalized.get("retrieval_text"))
        for field_name in ("keywords", "synonyms", "constraints"):
            normalized[field_name] = self._coerce_string_list(normalized.get(field_name))
        normalized["retrieval_text"] = self._compose_structured_retrieval_text(normalized)
        return normalized

    def _compose_structured_retrieval_text(self, payload: dict[str, Any]) -> str:
        parts = [
            self._coerce_text_block(payload.get("retrieval_text")),
            " ".join(self._coerce_string_list(payload.get("keywords"))),
            " ".join(self._coerce_string_list(payload.get("synonyms"))),
            " ".join(self._coerce_string_list(payload.get("constraints"))),
        ]
        return "\n".join(part for part in parts if part).strip()

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

    def _coerce_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                cleaned = str(item).strip()
                if cleaned:
                    result.append(cleaned)
            return result
        cleaned = str(value).strip()
        return [cleaned] if cleaned else []

    def _coerce_text_block(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return "\n".join(str(item).strip() for item in value if str(item).strip())
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
                                "malformed_content": self._truncate_text(malformed_content, 8000),
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


def build_retrieval_profile_provider(
    settings: Settings | None = None,
    *,
    client: httpx.Client | None = None,
) -> RetrievalProfileProvider:
    """Build the active retrieval profile provider from runtime settings."""

    resolved_settings = settings or get_settings()
    mode = resolved_settings.retrieval_profile_provider.lower().strip()
    if mode not in {"auto", "deepseek"}:
        raise ValueError(
            f"Unsupported RETRIEVAL_PROFILE_PROVIDER: {resolved_settings.retrieval_profile_provider}. "
            "Only 'deepseek' is supported in the formal chain."
        )
    if not resolved_settings.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is required because retrieval profile generation no longer supports deterministic fallback."
        )
    return DeepSeekRetrievalProfileProvider(
        api_key=resolved_settings.deepseek_api_key,
        model=resolved_settings.deepseek_model,
        base_url=resolved_settings.deepseek_api_base_url,
        timeout_seconds=resolved_settings.deepseek_timeout_seconds,
        client=client,
    )
