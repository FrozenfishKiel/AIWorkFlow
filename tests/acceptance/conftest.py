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

os.environ["TASK_GENERATION_PROVIDER"] = "deterministic"
os.environ["RETRIEVAL_PROFILE_PROVIDER"] = "deterministic"

import app.main as app_main
from app.core.db import get_session
from app.core.settings import get_settings
from app.main import app


@pytest.fixture()
def runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("APP_RUNTIME_DIR", str(runtime_root))
    get_settings.cache_clear()
    app_main.settings = get_settings()
    return runtime_root


@pytest.fixture()
def engine(runtime_dir: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
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
