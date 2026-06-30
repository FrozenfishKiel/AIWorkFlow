from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models import Task, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.schemas.task import ReviewRejectRequest, ReviewRerunRequest, ReviewUpdateRequest


class ReviewService:
    """Owns the review gate, reviewer snapshots, and export authority boundary.

    The important invariant in this service is that generated pipeline output is
    never exported directly after a reviewer starts making decisions. Reviewer
    edits live under ``task.review`` while the review is active, and only an
    explicit approval promotes a canonical ``approved_snapshot`` that downstream
    export is allowed to consume.
    """

    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def start_review(self, task_id: str | UUID) -> Task:
        """Move a task from generated output into active human review."""

        task = self.repository.require_task(task_id)
        if task.status != TaskStatus.REVIEW_PENDING:
            raise ValueError("Task is not ready for review.")

        existing_review = task.review or {}
        review = {
            "decision": "in_review",
            "reviewer_note": existing_review.get("reviewer_note"),
            "rejection_reason": None,
            "rerun_reason": existing_review.get("rerun_reason"),
            "not_adopted_items": existing_review.get("not_adopted_items", []),
            "edited_understanding": existing_review.get("edited_understanding"),
            "edited_retrieval_hits": existing_review.get("edited_retrieval_hits", []),
            "edited_workflow_result": existing_review.get("edited_workflow_result"),
        }
        return self.repository.save_review(task=task, status=TaskStatus.REVIEWING, review=review)

    def save_review(self, task_id: str | UUID, payload: ReviewUpdateRequest) -> Task:
        """Persist reviewer edits without promoting them to export authority."""

        task = self.repository.require_task(task_id)
        if task.status != TaskStatus.REVIEWING:
            raise ValueError("Task must be in reviewing before this action.")

        status = TaskStatus.REVIEWING
        review = self._build_review_snapshot(task=task, payload=payload, decision="in_review")
        return self.repository.save_review(task=task, status=status, review=review, approved_snapshot=None)

    def approve_review(self, task_id: str | UUID, payload: ReviewUpdateRequest) -> Task:
        """Approve reviewer edits and freeze the canonical export snapshot."""

        task = self.repository.require_task(task_id)
        if task.status != TaskStatus.REVIEWING:
            raise ValueError("Task must be in reviewing before this action.")

        review = self._build_review_snapshot(task=task, payload=payload, decision="approved")
        approved_snapshot = self._build_approved_snapshot(task=task, review=review)
        return self.repository.save_review(
            task=task,
            status=TaskStatus.APPROVED,
            review=review,
            approved_snapshot=approved_snapshot,
        )

    def reject_review(self, task_id: str | UUID, payload: ReviewRejectRequest) -> Task:
        """Reject the current result while retaining reviewer context for audit."""

        task = self.repository.require_task(task_id)
        if task.status != TaskStatus.REVIEWING:
            raise ValueError("Task must be in reviewing before this action.")

        existing_review = task.review or {}
        review = {
            "decision": "rejected",
            "reviewer_note": existing_review.get("reviewer_note"),
            "rejection_reason": payload.rejection_reason,
            "rerun_reason": None,
            "not_adopted_items": existing_review.get("not_adopted_items", []),
            "edited_understanding": existing_review.get("edited_understanding"),
            "edited_retrieval_hits": existing_review.get("edited_retrieval_hits", []),
            "edited_workflow_result": existing_review.get("edited_workflow_result"),
        }
        return self.repository.save_review(
            task=task,
            status=TaskStatus.REJECTED,
            review=review,
            approved_snapshot=None,
        )

    def ensure_rerun_allowed(self, task_id: str | UUID) -> None:
        """Fail fast when a rerun is requested from a non-rejected state.

        Routes call this before enqueueing Celery work so invalid state
        transitions cannot leak background jobs into the queue.
        """

        task = self.repository.require_task(task_id)
        if task.status != TaskStatus.REJECTED:
            raise ValueError("Task must be rejected before rerun.")

    def rerun_review(self, task_id: str | UUID, payload: ReviewRerunRequest) -> Task:
        """Requeue a rejected task and preserve why regeneration was requested."""

        task = self.repository.require_task(task_id)
        if task.status != TaskStatus.REJECTED:
            raise ValueError("Task must be rejected before rerun.")

        existing_review = task.review or {}
        review = {
            "decision": "rejected",
            "reviewer_note": existing_review.get("reviewer_note"),
            "rejection_reason": existing_review.get("rejection_reason"),
            "rerun_reason": payload.rerun_reason,
            "not_adopted_items": existing_review.get("not_adopted_items", []),
            "edited_understanding": existing_review.get("edited_understanding"),
            "edited_retrieval_hits": existing_review.get("edited_retrieval_hits", []),
            "edited_workflow_result": existing_review.get("edited_workflow_result"),
        }
        return self.repository.save_review(
            task=task,
            status=TaskStatus.QUEUED,
            review=review,
            approved_snapshot=None,
        )

    def _build_review_snapshot(
        self,
        *,
        task: Task,
        payload: ReviewUpdateRequest,
        decision: str,
    ) -> dict[str, Any]:
        """Merge reviewer edits onto the current review snapshot.

        ``None`` means "keep the current persisted value" for optional reviewed
        sections, which lets the UI save one edited area without accidentally
        wiping another area.
        """

        existing_review = task.review or {}
        return {
            "decision": decision,
            "reviewer_note": payload.reviewer_note,
            "rejection_reason": None,
            "rerun_reason": None,
            "not_adopted_items": payload.not_adopted_items,
            "edited_understanding": (
                payload.edited_understanding.model_dump()
                if payload.edited_understanding is not None
                else existing_review.get("edited_understanding")
            ),
            "edited_retrieval_hits": (
                [hit.model_dump() for hit in payload.edited_retrieval_hits]
                if payload.edited_retrieval_hits is not None
                else existing_review.get("edited_retrieval_hits", [])
            ),
            "edited_workflow_result": (
                payload.edited_workflow_result.model_dump()
                if payload.edited_workflow_result is not None
                else existing_review.get("edited_workflow_result")
            ),
        }

    def _build_approved_snapshot(self, *, task: Task, review: dict[str, Any]) -> dict[str, Any]:
        """Promote the reviewer-approved values into the export-owned snapshot."""

        return {
            "understanding": review.get("edited_understanding") or task.understanding,
            "retrieval_hits": review.get("edited_retrieval_hits") or task.retrieval_hits,
            "workflow_result": review.get("edited_workflow_result") or task.workflow_result,
        }
