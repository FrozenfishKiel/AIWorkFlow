from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.repositories.task_repository import TaskRepository
from app.schemas.task import ReviewRejectRequest, ReviewRerunRequest, ReviewUpdateRequest, TaskRead
from app.services.review_service import ReviewService
from app.tasks.task_runner import run_task_pipeline

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _review_service(session: Session) -> ReviewService:
    return ReviewService(TaskRepository(session))


@router.post("/{task_id}/start", response_model=TaskRead)
def start_review(task_id: UUID, session: Session = Depends(get_session)) -> TaskRead:
    """Move a review-pending task into active human review."""

    service = _review_service(session)
    try:
        task = service.start_review(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TaskRead.model_validate(task)


@router.put("/{task_id}", response_model=TaskRead)
def save_review(
    task_id: UUID,
    payload: ReviewUpdateRequest,
    session: Session = Depends(get_session),
) -> TaskRead:
    """Save reviewer edits without approving the task yet."""

    service = _review_service(session)
    try:
        task = service.save_review(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TaskRead.model_validate(task)


@router.post("/{task_id}/approve", response_model=TaskRead)
def approve_review(
    task_id: UUID,
    payload: ReviewUpdateRequest,
    session: Session = Depends(get_session),
) -> TaskRead:
    """Approve the current reviewer-adjusted task output."""

    service = _review_service(session)
    try:
        task = service.approve_review(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TaskRead.model_validate(task)


@router.post("/{task_id}/reject", response_model=TaskRead)
def reject_review(
    task_id: UUID,
    payload: ReviewRejectRequest,
    session: Session = Depends(get_session),
) -> TaskRead:
    """Reject the task and persist the rejection reason for auditability."""

    service = _review_service(session)
    try:
        task = service.reject_review(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TaskRead.model_validate(task)


@router.post("/{task_id}/rerun", response_model=TaskRead)
def rerun_review(
    task_id: UUID,
    payload: ReviewRerunRequest,
    session: Session = Depends(get_session),
) -> TaskRead:
    """Requeue a rejected task so the async pipeline can regenerate it.

    Validation happens before Celery enqueue so invalid states cannot create
    orphan background jobs that the reviewer never actually authorized.
    """

    service = _review_service(session)
    try:
        service.ensure_rerun_allowed(task_id)
        run_task_pipeline.delay(str(task_id))
        task = service.rerun_review(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TaskRead.model_validate(task)
