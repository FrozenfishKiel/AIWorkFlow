from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.repositories.task_repository import TaskRepository
from app.schemas.product_content import (
    GeneratedContentRead,
    ProductBriefRead,
    ProductContentJobCreateRequest,
    ProductContentJobRead,
    ProductInput,
    ReferenceContextRead,
)
from app.tasks.task_runner import run_task_pipeline

router = APIRouter(prefix="/product-content", tags=["product-content"])


def _enqueue_task_or_raise(repository: TaskRepository, task_id: str, task_for_cleanup) -> None:
    try:
        run_task_pipeline.delay(task_id)
    except Exception as exc:
        repository.delete_task(task_for_cleanup)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue is temporarily unavailable.",
        ) from exc


def _parse_product_request(content: str) -> tuple[ProductInput, str]:
    payload = json.loads(content)
    product = ProductInput.model_validate(payload["product"])
    task_description = str(payload["task_description"]).strip()
    return product, task_description


def _to_job_read(task) -> ProductContentJobRead:
    product, task_description = _parse_product_request(task.content)
    product_brief = None
    if task.understanding:
        product_brief = ProductBriefRead.model_validate(task.understanding)

    reference_context = [
        ReferenceContextRead.model_validate(hit)
        for hit in (task.retrieval_hits or [])
    ]

    generated_content = None
    if task.workflow_result:
        generated_content = GeneratedContentRead.model_validate(task.workflow_result)

    return ProductContentJobRead(
        id=task.id,
        status=task.status,
        current_stage=task.current_stage,
        error_message=task.error_message,
        product=product,
        task_description=task_description,
        product_brief=product_brief,
        reference_context=reference_context,
        generated_content=generated_content,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/jobs", response_model=ProductContentJobRead, status_code=status.HTTP_201_CREATED)
def create_product_content_job(
    payload: ProductContentJobCreateRequest,
    session: Session = Depends(get_session),
) -> ProductContentJobRead:
    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="product_request",
        content=json.dumps(payload.model_dump(), ensure_ascii=False),
        knowledge_domain="ecommerce",
    )
    _enqueue_task_or_raise(repository, str(task.id), task)
    return _to_job_read(task)


@router.get("/jobs/{task_id}", response_model=ProductContentJobRead)
def get_product_content_job(task_id: UUID, session: Session = Depends(get_session)) -> ProductContentJobRead:
    repository = TaskRepository(session)
    task = repository.get_task(task_id)
    if task is None or task.input_type != "product_request":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product content job not found.")
    return _to_job_read(task)
