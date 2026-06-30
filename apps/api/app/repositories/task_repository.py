from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.models import Task, TaskStatus


class TaskRepository:
    """Persistence helpers for task entities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_task(self, *, input_type: str, content: str, knowledge_domain: str | None = None) -> Task:
        task = Task(input_type=input_type, content=content, knowledge_domain=knowledge_domain)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def delete_task(self, task: Task) -> None:
        """Remove a task that never safely entered the async queue."""

        self.session.delete(task)
        self.session.commit()

    def list_tasks(self) -> list[Task]:
        statement = select(Task).order_by(Task.created_at.desc())
        return list(self.session.exec(statement))

    def get_task(self, task_id: str | UUID) -> Task | None:
        task_uuid = UUID(str(task_id))
        return self.session.get(Task, task_uuid)

    def require_task(self, task_id: str | UUID) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise LookupError(f"Task not found: {task_id}")
        return task

    def update_status(
        self,
        *,
        task: Task,
        status: TaskStatus,
        error_message: str | None = None,
    ) -> Task:
        """Persist a stage transition and keep status/current_stage in lockstep.

        The first slice uses one visible stage field for the polling UI, so the
        repository updates both values together instead of letting them drift.
        """

        task.status = status
        task.current_stage = status
        task.error_message = error_message
        task.updated_at = datetime.now(timezone.utc)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def update_pipeline_results(
        self,
        *,
        task: Task,
        status: TaskStatus,
        understanding: dict[str, object],
        retrieval_hits: list[dict[str, object]],
        workflow_result: dict[str, object],
    ) -> Task:
        """Store the structured outputs for the completed pre-review pipeline.

        Successful pipeline completion also clears any prior error so re-runs do
        not leave stale failure messages attached to reviewer-visible results.
        """

        task.status = status
        task.current_stage = status
        task.error_message = None
        task.understanding = understanding
        task.retrieval_hits = retrieval_hits
        task.workflow_result = workflow_result
        task.updated_at = datetime.now(timezone.utc)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def save_review(
        self,
        *,
        task: Task,
        status: TaskStatus,
        review: dict[str, object],
        approved_snapshot: dict[str, object] | None = None,
    ) -> Task:
        """Persist the current human review snapshot and aligned task status."""

        task.status = status
        task.current_stage = status
        task.error_message = None
        task.review = review
        task.approved_snapshot = approved_snapshot
        task.updated_at = datetime.now(timezone.utc)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task
