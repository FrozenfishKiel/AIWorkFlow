from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session

from app.core.db import get_session
from app.core.settings import get_settings
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.audit import AuditLogRead
from app.schemas.task import TaskCreateRequest, TaskRead
from app.services.input_security import validate_public_url
from app.tasks.task_runner import run_task_pipeline

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _enqueue_task_or_raise(repository: TaskRepository, task_id: str, task_for_cleanup) -> None:
    """Enqueue the task or fail fast without leaving orphan queued records.

    The route has already persisted a task by the time this helper runs, so an
    enqueue failure must clean that record up instead of pretending a worker is
    coming later.
    """

    try:
        run_task_pipeline.delay(task_id)
    except Exception as exc:
        repository.delete_task(task_for_cleanup)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue is temporarily unavailable.",
        ) from exc


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreateRequest,
    session: Session = Depends(get_session),
) -> TaskRead:
    """Create a text or URL task and hand the slow work to Celery immediately."""

    if payload.input_type == "url":
        validate_public_url(payload.content)

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type=payload.input_type,
        content=payload.content,
        knowledge_domain=payload.knowledge_domain,
    )
    _enqueue_task_or_raise(repository, str(task.id), task)
    return TaskRead.model_validate(task)


@router.post(
    "/upload",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_file_task(
    file: UploadFile = File(...),
    knowledge_domain: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> TaskRead:
    """Accept a bounded file upload, store it safely, then enqueue async parsing.

    The endpoint strips any client-provided path segments, enforces extension and
    size limits up front, and rewrites duplicate filenames so audit trails do not
    silently point multiple tasks at the same on-disk artifact.
    """

    settings = get_settings()
    extension = Path(file.filename or "").suffix.lower()
    if extension not in settings.allowed_upload_extensions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type.",
        )

    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large.",
        )

    safe_name = Path(file.filename or "upload").name
    destination = settings.uploads_root / safe_name
    if destination.exists():
        destination = settings.uploads_root / f"{destination.stem}-{uuid4().hex}{destination.suffix}"
    destination.write_bytes(contents)

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="file",
        content=str(destination),
        knowledge_domain=knowledge_domain,
    )
    _enqueue_task_or_raise(repository, str(task.id), task)
    return TaskRead.model_validate(task)


@router.get("", response_model=list[TaskRead])
def list_tasks(session: Session = Depends(get_session)) -> list[TaskRead]:
    """Return task summaries ordered by newest first for the console list view."""

    repository = TaskRepository(session)
    tasks = repository.list_tasks()
    return [TaskRead.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, session: Session = Depends(get_session)) -> TaskRead:
    """Return the latest persisted task detail for polling and review screens."""

    repository = TaskRepository(session)
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )
    return TaskRead.model_validate(task)


@router.get("/{task_id}/audit-logs", response_model=list[AuditLogRead])
def list_task_audit_logs(task_id: UUID, session: Session = Depends(get_session)) -> list[AuditLogRead]:
    """Return the latest-first action timeline for one task."""

    task_repository = TaskRepository(session)
    if task_repository.get_task(task_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    audit_repository = AuditLogRepository(session)
    return [AuditLogRead.model_validate(item) for item in audit_repository.list_for_task(task_id)]
