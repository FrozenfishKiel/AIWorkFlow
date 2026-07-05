from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.db import get_session
from app.models import TaskStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.audit import AuditLogRead
from app.schemas.product_content import (
    GeneratedContentRead,
    ProductContentDiagnosticsRead,
    ProductBriefRead,
    ProductContentJobCreateRequest,
    ProductContentJobRead,
    ProductInput,
    ReferenceContextRead,
    SellingStrategyRead,
)
from app.services.inline_background_fallback import (
    run_task_pipeline_inline,
    should_use_inline_background_fallback,
)
from app.tasks.task_runner import run_task_pipeline

router = APIRouter(prefix="/product-content", tags=["product-content"])


def _enqueue_task_or_raise(
    repository: TaskRepository,
    session: Session,
    task_id: str,
    task_for_cleanup,
) -> None:
    try:
        run_task_pipeline.delay(task_id)
    except Exception as exc:
        if should_use_inline_background_fallback():
            try:
                run_task_pipeline_inline(session, task_id)
            except Exception:
                session.expire_all()
                if repository.require_task(task_id).status == TaskStatus.FAILED:
                    return
                raise
            return
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


def _to_reference_context_item(
    hit: dict[str, object],
    *,
    rank: int | None = None,
    selected_source_ids: set[str] | None = None,
) -> ReferenceContextRead:
    selected_ids = selected_source_ids or set()
    payload = {
        **hit,
        "rank": rank,
        "selected": str(hit.get("source_id") or "") in selected_ids,
    }
    return ReferenceContextRead.model_validate(payload)


def _build_task_diagnostics(task, audit_repository: AuditLogRepository) -> ProductContentDiagnosticsRead | None:
    workflow_diagnostics = ((task.workflow_result or {}).get("diagnostics") or None)
    if workflow_diagnostics:
        return ProductContentDiagnosticsRead.model_validate(workflow_diagnostics)

    if task.status.value != "failed":
        return None

    for item in audit_repository.list_for_task(task.id):
        if item.event_type.value != "pipeline_failed":
            continue
        return ProductContentDiagnosticsRead.model_validate(item.details)

    return ProductContentDiagnosticsRead(
        generation_provider="",
        retrieval_provider="",
        retrieval_query="",
        failure_stage=task.current_stage,
        failure_reason=task.error_message,
    )


def _to_job_read(task, audit_repository: AuditLogRepository) -> ProductContentJobRead:
    product, task_description = _parse_product_request(task.content)
    product_brief = None
    if task.understanding:
        product_brief = ProductBriefRead.model_validate(task.understanding)

    diagnostics = _build_task_diagnostics(task, audit_repository)
    selected_source_ids = set(diagnostics.selected_source_ids) if diagnostics else set()
    selected_evidence_payload = (task.workflow_result or {}).get("evidence_used") or task.retrieval_hits or []
    reference_context = [
        _to_reference_context_item(hit, selected_source_ids=selected_source_ids)
        for hit in selected_evidence_payload
    ]
    retrieval_candidates = [
        _to_reference_context_item(
            hit,
            rank=index + 1,
            selected_source_ids=selected_source_ids,
        )
        for index, hit in enumerate(task.retrieval_hits or [])
    ]

    generated_content = None
    if task.workflow_result:
        generated_content = GeneratedContentRead.model_validate(task.workflow_result)

    selling_strategy = None
    if task.workflow_result and task.workflow_result.get("selling_strategy"):
        selling_strategy = SellingStrategyRead.model_validate(task.workflow_result["selling_strategy"])

    input_alerts = [
        str(item).strip()
        for item in ((task.understanding or {}).get("input_alerts", []))
        if str(item).strip()
    ]
    context_summary = dict((task.workflow_result or {}).get("context_summary") or {})
    processing_trace = [
        str(item).strip()
        for item in ((task.workflow_result or {}).get("processing_trace") or [])
        if str(item).strip()
    ]

    return ProductContentJobRead(
        id=task.id,
        status=task.status,
        current_stage=task.current_stage,
        error_message=task.error_message,
        product=product,
        task_description=task_description,
        product_brief=product_brief,
        selling_strategy=selling_strategy,
        input_alerts=input_alerts,
        reference_context=reference_context,
        retrieval_candidates=retrieval_candidates,
        context_summary=context_summary,
        diagnostics=diagnostics,
        processing_trace=processing_trace,
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
    _enqueue_task_or_raise(repository, session, str(task.id), task)
    session.expire_all()
    refreshed_task = repository.require_task(task.id)
    return _to_job_read(refreshed_task, AuditLogRepository(session))


@router.get("/jobs/{task_id}", response_model=ProductContentJobRead)
def get_product_content_job(task_id: UUID, session: Session = Depends(get_session)) -> ProductContentJobRead:
    repository = TaskRepository(session)
    task = repository.get_task(task_id)
    if task is None or task.input_type != "product_request":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product content job not found.")
    return _to_job_read(task, AuditLogRepository(session))


@router.get("/jobs/{task_id}/audit-logs", response_model=list[AuditLogRead])
def list_product_content_job_audit_logs(
    task_id: UUID,
    session: Session = Depends(get_session),
) -> list[AuditLogRead]:
    repository = TaskRepository(session)
    task = repository.get_task(task_id)
    if task is None or task.input_type != "product_request":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product content job not found.")

    audit_repository = AuditLogRepository(session)
    return [AuditLogRead.model_validate(item) for item in audit_repository.list_for_task(task_id)]
