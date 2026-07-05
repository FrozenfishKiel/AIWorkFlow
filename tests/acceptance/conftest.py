from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import os

os.environ["TASK_GENERATION_PROVIDER"] = "deepseek"
os.environ["RETRIEVAL_PROFILE_PROVIDER"] = "deepseek"
os.environ["DEEPSEEK_API_KEY"] = "test-key"

import app.main as app_main
from app.core.db import get_session
from app.core.settings import get_settings
from app.main import app
from app.services.default_ecommerce_knowledge import ensure_default_ecommerce_knowledge


class _FakeTaskGenerationProvider:
    provider_name = "fake-deepseek-acceptance-provider"

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
        return {
            "summary": f"Structured summary for: {str(parsed_input['parsed_text'])[:80].strip()}",
            "audience": ["content-ops", "brand"],
            "key_points": ["Need structured understanding before generation."],
            "risk_points": ["Claims still require verification."],
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
            return {
                "selling_points_copy": [f"{name}先讲核心卖点，再讲真实使用场景。"],
                "detail_page_copy": f"{name}详情页先讲核心体验，再补规格与活动信息。",
                "social_seed_copy": f"{name}种草文案优先强调真实体验。",
                "risk_notes": ["避免使用绝对化表达。"],
                "applied_guidelines": [str(hit['title']) for hit in retrieval_hits],
            }
        return {
            "draft": "Draft workflow result based on structured understanding.",
            "review_notes": ["Confirm the final business angle before external use."],
            "open_questions": ["Are any claims missing manual confirmation?"],
            "manual_checks": ["Verify every externally visible claim against the cited evidence."],
        }


class _FakeRetrievalProfileProvider:
    provider_name = "fake-deepseek-acceptance-retrieval-profile"

    def build_chunk_profile(self, *, title: str, content: str, domain: str, source_type: str) -> dict[str, object]:
        retrieval_text = "\n".join(part for part in [title.strip(), content.strip(), domain, source_type] if part)
        return {
            "retrieval_text": retrieval_text,
            "keywords": [],
            "synonyms": [],
            "constraints": [item for item in [domain, source_type] if item],
        }

    def build_query_profile(self, *, query_text: str, domain: str | None) -> dict[str, object]:
        return {
            "retrieval_text": query_text,
            "keywords": [],
            "synonyms": [],
            "constraints": [domain] if domain else [],
        }


@pytest.fixture()
def runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("APP_RUNTIME_DIR", str(runtime_root))
    get_settings.cache_clear()
    app_main.settings = get_settings()
    return runtime_root


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
def engine(runtime_dir: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ensure_default_ecommerce_knowledge(session)
    return engine


@pytest.fixture()
def client(engine) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as db_session:
            yield db_session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
