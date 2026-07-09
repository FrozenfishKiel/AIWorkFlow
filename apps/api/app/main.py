from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials

from app.api.routes_auth import router as auth_router
from app.api.routes_exports import router as exports_router
from app.api.routes_knowledge import router as knowledge_router
from app.api.routes_product_content import router as product_content_router
from app.api.routes_runtime_config import router as runtime_config_router
from app.core.db import init_db, session_scope
from app.core.logging import configure_logging
from app.core.security import bearer_scheme, require_authenticated_user
from app.core.settings import get_settings
from app.services.default_ecommerce_knowledge import ensure_default_ecommerce_knowledge

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize logging and persistence before serving requests."""

    configure_logging()
    init_db()
    with session_scope() as session:
        ensure_default_ecommerce_knowledge(session)
    yield


app = FastAPI(
    title="电商商品内容生产系统 API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _require_access_token_dependency(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    require_authenticated_user(request, credentials)


app.include_router(auth_router)
app.include_router(runtime_config_router)
app.include_router(exports_router, dependencies=[Depends(_require_access_token_dependency)])
app.include_router(knowledge_router, dependencies=[Depends(_require_access_token_dependency)])
app.include_router(product_content_router, dependencies=[Depends(_require_access_token_dependency)])


@app.get("/health")
def health() -> dict[str, str]:
    """Return a minimal health signal for local compose and smoke checks."""

    return {"status": "ok"}
