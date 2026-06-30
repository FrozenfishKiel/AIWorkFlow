from __future__ import annotations

from mimetypes import guess_type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.core.db import get_session
from app.repositories.export_job_repository import ExportJobRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import ExportJobCreateRequest, ExportJobRead
from app.services.export_service import ExportService
from app.tasks.export_runner import run_export_job

router = APIRouter(prefix="/exports", tags=["exports"])


def _export_service(session: Session) -> ExportService:
    return ExportService(TaskRepository(session), ExportJobRepository(session))


@router.post("", response_model=ExportJobRead, status_code=status.HTTP_201_CREATED)
def create_export_job(
    payload: ExportJobCreateRequest,
    session: Session = Depends(get_session),
) -> ExportJobRead:
    """Create an export job for an approved task and enqueue async generation."""

    service = _export_service(session)
    try:
        job = service.create_export_job(task_id=payload.task_id, export_type=payload.export_type)
        run_export_job.delay(str(job.id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    repository = ExportJobRepository(session)
    return ExportJobRead.model_validate(repository.require_job(job.id))


@router.get("/{export_job_id}", response_model=ExportJobRead)
def get_export_job(export_job_id: UUID, session: Session = Depends(get_session)) -> ExportJobRead:
    """Return the current export job status and generated artifact path."""

    repository = ExportJobRepository(session)
    job = repository.get_job(export_job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found.")
    return ExportJobRead.model_validate(job)


@router.get("/{export_job_id}/artifact")
def download_export_artifact(export_job_id: UUID, session: Session = Depends(get_session)) -> FileResponse:
    """Download the completed artifact through the API instead of exposing raw paths."""

    service = _export_service(session)
    try:
        artifact_path = service.resolve_artifact_path(export_job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export artifact file is missing.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    media_type, _ = guess_type(artifact_path.name)
    return FileResponse(
        artifact_path,
        media_type=media_type or "application/octet-stream",
        filename=artifact_path.name,
    )
