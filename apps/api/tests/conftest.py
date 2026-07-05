import os
import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ["TASK_GENERATION_PROVIDER"] = "deepseek"
os.environ["RETRIEVAL_PROFILE_PROVIDER"] = "deepseek"
os.environ["DEEPSEEK_API_KEY"] = "test-key"

from app.core.db import get_session
from app.main import app


class _FakeTaskGenerationProvider:
    provider_name = "fake-deepseek-test-provider"

    def build_understanding(self, parsed_input: dict[str, object]) -> dict[str, object]:
        if parsed_input["source_kind"] == "product_request":
            product_payload = parsed_input["product_payload"]
            name = str(product_payload.get("name") or "商品")
            target_audience = str(product_payload.get("target_audience") or "目标用户")
            scenarios = [str(item) for item in product_payload.get("use_scenarios", [])]
            selling_points = [str(item) for item in product_payload.get("core_selling_points", [])]
            return {
                "summary": f"{name}面向{target_audience}，本次应重点突出{'、'.join(selling_points[:3]) or '核心卖点'}。",
                "target_audience": target_audience,
                "use_scenarios": scenarios,
                "primary_value_points": selling_points[:3],
            }

        parsed_text = str(parsed_input["parsed_text"])
        snippet = parsed_text[:80].strip() or "No content provided."
        return {
            "summary": f"Structured summary for: {snippet}",
            "audience": ["content-ops", "brand"],
            "key_points": [
                "The task requires structured understanding before generation.",
                "References should remain visible in the persisted record.",
                "Results should remain exportable without synchronous approval.",
            ],
            "risk_points": ["Claims still require post-run verification against cited evidence."],
            "uncertain_items": ["Final business angle may still need operator confirmation."],
        }

    def build_workflow(
        self,
        *,
        parsed_input: dict[str, object],
        understanding: dict[str, object],
        retrieval_hits: list[dict[str, object]],
        generation_context: dict[str, object],
    ) -> dict[str, object]:
        if parsed_input["source_kind"] == "product_request":
            product_payload = parsed_input["product_payload"]
            name = str(product_payload.get("name") or "商品")
            selling_strategy = generation_context.get("selling_strategy", {})
            selling_points = [str(item) for item in product_payload.get("core_selling_points", [])]
            guideline_titles = [str(hit["title"]) for hit in retrieval_hits]
            primary_angle = str(selling_strategy.get("primary_angle") or "").strip()
            supporting_angles = [
                str(item).strip()
                for item in selling_strategy.get("supporting_angles", [])
                if str(item).strip()
            ]
            scenario_focus = [
                str(item).strip()
                for item in selling_strategy.get("scenario_focus", [])
                if str(item).strip()
            ]
            expression_guardrails = [
                str(item).strip()
                for item in selling_strategy.get("expression_guardrails", [])
                if str(item).strip()
            ]
            first_line = (
                f"{name}{primary_angle or selling_points[0]}，更适合{understanding.get('target_audience') or '目标用户'}日常使用。"
                if primary_angle or selling_points
                else f"{name}围绕真实使用场景整理了更清晰的卖点表达。"
            )
            return {
                "selling_points_copy": [
                    first_line,
                    (
                        f"围绕{'、'.join(scenario_focus[:2]) or '日常场景'}组织信息，"
                        f"同步补充{'、'.join(supporting_angles[:2]) or '次级卖点'}，更方便运营继续改写。"
                    ),
                ],
                "detail_page_copy": (
                    f"{name}这次主打{'、'.join(([primary_angle] if primary_angle else []) + supporting_angles[:2]) or '核心卖点'}，"
                    f"适合{'、'.join(scenario_focus[:2]) or '日常使用'}场景，"
                    "详情页建议先讲核心体验，再补充规格与活动信息。"
                ),
                "social_seed_copy": (
                    f"{name}这版种草文案先强调真实体验和使用场景，"
                    f"更适合面向{understanding.get('target_audience') or '目标用户'}继续打磨。"
                ),
                "risk_notes": expression_guardrails[:2] or ["避免使用绝对化功效承诺，保持真实体验表达。"],
                "applied_guidelines": guideline_titles,
            }

        source_ids = ", ".join(hit["source_id"] for hit in retrieval_hits)
        return {
            "draft": (
                "Draft workflow result based on the structured understanding and visible retrieval hits. "
                f"Primary audience: {', '.join(understanding['audience'])}."
            ),
            "review_notes": [
                "Confirm the final business angle before external use.",
                (
                    f"Verify the cited sources: {source_ids}."
                    if retrieval_hits
                    else "No indexed knowledge hits were available for this task yet."
                ),
            ],
            "open_questions": [
                "Does the generated angle match the brand constraint?",
                "Are any claims missing manual confirmation?",
            ],
            "manual_checks": [
                "Confirm the final business angle before external use.",
                "Verify every externally visible claim against the cited evidence.",
            ],
        }


class _FakeRetrievalProfileProvider:
    provider_name = "fake-deepseek-retrieval-profile"

    _token_pattern = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff\-]{2,}")
    _token_synonyms = {
        "sign-off": "approval",
        "signoffs": "approval",
        "signoff": "approval",
        "externally": "public",
        "external": "public",
        "visible": "public",
    }
    _query_noise_terms = {
        "商品", "产品", "任务", "描述", "内容", "文案", "生成", "输出", "需要", "想写", "帮我写", "一版", "突出", "当前",
    }
    _phrase_synonym_map = {
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
    _constraint_phrases = ("小红书", "种草", "详情页", "卖点", "直播", "短视频")

    def build_chunk_profile(
        self,
        *,
        title: str,
        content: str,
        domain: str,
        source_type: str,
    ) -> dict[str, object]:
        keywords = self._select_keywords(f"{title} {content}")
        synonyms = self._expand_synonyms(f"{title} {content}", keywords)
        constraints = self._dedupe_preserve_order([domain, source_type, *self._detect_constraints(f"{title} {content}")])
        retrieval_text = self._compose_retrieval_text(
            title=title,
            body=content,
            keywords=keywords,
            synonyms=synonyms,
            extra_terms=constraints,
        )
        return {
            "retrieval_text": retrieval_text,
            "keywords": keywords,
            "synonyms": synonyms,
            "constraints": constraints,
        }

    def build_query_profile(
        self,
        *,
        query_text: str,
        domain: str | None,
    ) -> dict[str, object]:
        keywords = self._select_keywords(query_text)
        synonyms = self._expand_synonyms(query_text, keywords)
        constraints = self._dedupe_preserve_order([domain, *self._detect_constraints(query_text)])
        if domain == "ecommerce":
            if any(marker in query_text for marker in ("小红书", "种草")) and "小红书" not in constraints:
                constraints.append("小红书")
            if any(marker in query_text for marker in ("真实使用感", "真实体验", "使用感", "场景感")):
                for synonym in ("真实体验", "场景感", "使用感"):
                    if synonym not in synonyms:
                        synonyms.append(synonym)
        return {
            "retrieval_text": self._compose_retrieval_text(
                title="query",
                body=query_text,
                keywords=keywords,
                synonyms=synonyms,
                extra_terms=constraints,
            ),
            "keywords": keywords,
            "synonyms": synonyms,
            "constraints": constraints,
        }

    def _compose_retrieval_text(
        self,
        *,
        title: str,
        body: str,
        keywords: list[str],
        synonyms: list[str],
        extra_terms: list[str],
    ) -> str:
        parts: list[str] = [title.strip(), body.strip()]
        if keywords:
            parts.append(" ".join(keywords))
        if synonyms:
            parts.append(" ".join(synonyms))
        filtered_extra_terms = [term for term in extra_terms if term]
        if filtered_extra_terms:
            parts.append(" ".join(filtered_extra_terms))
        return "\n".join(part for part in parts if part)

    def _extract_terms(self, text: str) -> list[str]:
        return [self._normalize_token(token) for token in self._token_pattern.findall(text)]

    def _select_keywords(self, text: str) -> list[str]:
        candidates = self._dedupe_preserve_order([
            *self._detect_phrase_signals(text),
            *self._extract_terms(text),
        ])
        filtered = [
            candidate
            for candidate in candidates
            if candidate and candidate not in self._query_noise_terms and len(candidate) <= 24
        ]
        return filtered[:12]

    def _expand_synonyms(self, text: str, keywords: list[str]) -> list[str]:
        expanded: list[str] = []
        normalized_text = text.lower()
        for candidate in [*keywords, *self._detect_phrase_signals(text)]:
            for synonym in self._phrase_synonym_map.get(candidate, []):
                expanded.append(synonym)
        if "approval" in normalized_text:
            expanded.extend(self._phrase_synonym_map["approval"])
        if "public" in normalized_text:
            expanded.extend(self._phrase_synonym_map["public"])
        if any(marker in text for marker in ("小红书", "种草", "真实使用感", "真实体验", "使用感", "场景感")):
            expanded.extend(["真实体验", "场景感", "使用感"])
        return self._dedupe_preserve_order(expanded)

    def _detect_constraints(self, text: str) -> list[str]:
        return [phrase for phrase in self._constraint_phrases if phrase in text]

    def _detect_phrase_signals(self, text: str) -> list[str]:
        return [phrase for phrase in self._phrase_candidates() if phrase in text]

    def _phrase_candidates(self) -> list[str]:
        return self._dedupe_preserve_order([*self._phrase_synonym_map.keys(), *self._constraint_phrases])

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            cleaned = str(item).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result

    def _normalize_token(self, token: str) -> str:
        normalized = token.lower()
        normalized = self._token_synonyms.get(normalized, normalized)
        if normalized.endswith("ies") and len(normalized) > 4:
            normalized = normalized[:-3] + "y"
        elif normalized.endswith("s") and len(normalized) > 4 and not normalized.endswith("ss"):
            normalized = normalized[:-1]
        return self._token_synonyms.get(normalized, normalized)


@pytest.fixture(autouse=True)
def fake_model_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.task_pipeline_service.build_task_generation_provider",
        lambda: _FakeTaskGenerationProvider(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_index_service.build_retrieval_profile_provider",
        lambda: _FakeRetrievalProfileProvider(),
    )
    monkeypatch.setattr(
        "app.services.retrieval_service.build_retrieval_profile_provider",
        lambda: _FakeRetrievalProfileProvider(),
    )


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session(engine) -> Generator[Session, None, None]:
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture()
def client(engine) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as db_session:
            yield db_session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
