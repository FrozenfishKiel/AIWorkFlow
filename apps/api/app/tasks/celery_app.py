from __future__ import annotations

from celery import Celery

from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_content_ops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.task_runner",
        "app.tasks.export_runner",
        "app.tasks.knowledge_indexer",
    ],
)

# Keep task payloads portable across API/worker boundaries and make worker start
# events visible during polling and incident triage.
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
)
