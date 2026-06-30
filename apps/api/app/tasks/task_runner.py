from __future__ import annotations

import logging

from sqlmodel import Session

from app.core.db import engine
from app.models import TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.task_pipeline_service import TaskPipelineService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.run_task_pipeline")
def run_task_pipeline(task_id: str) -> dict[str, str]:
    """Execute the main async pipeline for a single task.

    The worker catches broad failures so an operator polling the API sees the
    task transition into ``failed`` instead of leaving a stuck in-flight status
    after the worker process crashes out of the pipeline.
    """

    try:
        service = TaskPipelineService(lambda: Session(engine))
        processed_task = service.run_pipeline(task_id)
        return {
            "task_id": str(processed_task.id),
            "status": processed_task.status,
        }
    except Exception as exc:  # pragma: no cover - worker failure path
        logger.exception("Task pipeline failed for %s", task_id)
        with Session(engine) as session:
            repository = TaskRepository(session)
            task = repository.get_task(task_id)
            if task is not None:
                repository.update_status(
                    task=task,
                    status=TaskStatus.FAILED,
                    error_message=str(exc),
                )
        raise
