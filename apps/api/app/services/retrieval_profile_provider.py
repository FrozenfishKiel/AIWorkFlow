from __future__ import annotations

import json
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


class DeterministicRetrievalProfileProvider:
    """Fallback semantic profile builder for offline and test environments."""

    provider_name = "deterministic-retrieval-profile"

    def build_chunk_profile(
        self,
        *,
        title: str,
        content: str,
        domain: str,
        source_type: str,
    ) -> dict[str, Any]:
        terms = self._extract_terms(f"{title} {content}")
        keywords = terms[:12]
        retrieval_text = self._compose_retrieval_text(
            title=title,
            body=content,
            keywords=keywords,
            extra_terms=[domain, source_type],
        )
        return RetrievalProfilePayload(
            retrieval_text=retrieval_text,
            keywords=keywords,
            synonyms=[],
            constraints=[domain, source_type],
        ).model_dump()

    def build_query_profile(
        self,
        *,
        query_text: str,
        domain: str | None,
    ) -> dict[str, Any]:
        keywords = self._extract_terms(query_text)[:12]
        retrieval_text = self._compose_retrieval_text(
            title="query",
            body=query_text,
            keywords=keywords,
            extra_terms=[domain] if domain else [],
        )
        return RetrievalProfilePayload(
            retrieval_text=retrieval_text,
            keywords=keywords,
            synonyms=[],
            constraints=[domain] if domain else [],
        ).model_dump()

    def _compose_retrieval_text(
        self,
        *,
        title: str,
        body: str,
        keywords: list[str],
        extra_terms: list[str],
    ) -> str:
        parts: list[str] = [title.strip(), body.strip()]
        if keywords:
            parts.append("keywords: " + ", ".join(keywords))
        filtered_extra_terms = [term for term in extra_terms if term]
        if filtered_extra_terms:
            parts.append("constraints: " + ", ".join(filtered_extra_terms))
        return "\n".join(part for part in parts if part)

    def _extract_terms(self, text: str) -> list[str]:
        return [self._normalize_token(token) for token in TOKEN_PATTERN.findall(text)]

    def _normalize_token(self, token: str) -> str:
        normalized = token.lower()
        normalized = TOKEN_SYNONYMS.get(normalized, normalized)

        if normalized.endswith("ies") and len(normalized) > 4:
            normalized = normalized[:-3] + "y"
        elif normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith("ss"):
            normalized = normalized[:-1]

        return TOKEN_SYNONYMS.get(normalized, normalized)


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
                "You build retrieval profiles for a content-ops knowledge base. "
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
                "You normalize user retrieval queries for a content-ops knowledge base. "
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
        return json.loads(content)

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["retrieval_text"] = self._coerce_text_block(normalized.get("retrieval_text"))
        for field_name in ("keywords", "synonyms", "constraints"):
            normalized[field_name] = self._coerce_string_list(normalized.get(field_name))
        return normalized

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


def build_retrieval_profile_provider(
    settings: Settings | None = None,
    *,
    client: httpx.Client | None = None,
) -> RetrievalProfileProvider:
    """Build the active retrieval profile provider from runtime settings."""

    resolved_settings = settings or get_settings()
    mode = resolved_settings.retrieval_profile_provider.lower().strip()

    if mode == "deepseek" or (mode == "auto" and resolved_settings.deepseek_api_key):
        if not resolved_settings.deepseek_api_key:
            raise ValueError(
                "RETRIEVAL_PROFILE_PROVIDER is set to 'deepseek' but no DEEPSEEK_API_KEY is configured."
            )
        return DeepSeekRetrievalProfileProvider(
            api_key=resolved_settings.deepseek_api_key,
            model=resolved_settings.deepseek_model,
            base_url=resolved_settings.deepseek_api_base_url,
            timeout_seconds=resolved_settings.deepseek_timeout_seconds,
            client=client,
        )

    return DeterministicRetrievalProfileProvider()
