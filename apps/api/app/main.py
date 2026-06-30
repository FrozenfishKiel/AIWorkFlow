from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials

from app.api.routes_exports import router as exports_router
from app.api.routes_knowledge import router as knowledge_router
from app.api.routes_reviews import router as reviews_router
from app.api.routes_tasks import router as tasks_router
from app.core.db import init_db
from app.core.logging import configure_logging
from app.core.security import bearer_scheme, require_access_token
from app.core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Content Production and Ops Workflow API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

protected_route_dependencies = [
    Depends(bearer_scheme),
]


def _require_access_token_dependency(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    require_access_token(credentials)


app.include_router(exports_router, dependencies=[Depends(_require_access_token_dependency)])
app.include_router(knowledge_router, dependencies=[Depends(_require_access_token_dependency)])
app.include_router(reviews_router, dependencies=[Depends(_require_access_token_dependency)])
app.include_router(tasks_router, dependencies=[Depends(_require_access_token_dependency)])


@app.on_event("startup")
def on_startup() -> None:
    """Initialize logging and persistence before serving requests."""

    configure_logging()
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    """Return a minimal health signal for local compose and smoke checks."""

    return {"status": "ok"}
