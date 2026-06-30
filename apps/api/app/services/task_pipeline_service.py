from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.models import Task, TaskStatus
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.task_repository import TaskRepository
from app.services.retrieval_service import RetrievalService
from app.services.url_ingestion_service import UrlIngestionService
from app.workflows.context_builder import ContextBuilder


class TaskPipelineService:
    """Runs the deterministic placeholder pipeline until live AI steps are wired in.

    The step order mirrors the intended production chain on purpose so the UI,
    persistence layer, and worker orchestration can stabilize before model and
    RAG integrations are swapped in.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory
        self.url_ingestion_service = UrlIngestionService()
        self.context_builder = ContextBuilder()

    def run_pipeline(self, task_id: str | UUID) -> Task:
        """Execute the pipeline one stage at a time and persist each state change.

        Persisting state before each synthetic stage keeps the polling UI and the
        failure path honest, instead of pretending the whole task is one opaque
        background step.
        """

        with self.session_factory() as session:
            repository = TaskRepository(session)
            task = repository.require_task(task_id)
            processing_trace: list[str] = []

            repository.update_status(task=task, status=TaskStatus.PARSING)
            parsed_input = self._parse_input(task.input_type, task.content)
            processing_trace.extend(parsed_input["processing_trace"])

            repository.update_status(task=task, status=TaskStatus.UNDERSTANDING)
            understanding = self._build_understanding(parsed_input)
            processing_trace.append("Built structured understanding with risk and uncertainty markers.")

            repository.update_status(task=task, status=TaskStatus.RETRIEVING)
            retrieval_hits = self._build_retrieval_hits(
                session,
                parsed_input["retrieval_query"],
                knowledge_domain=task.knowledge_domain,
            )
            processing_trace.append(
                f"Retrieved {len(retrieval_hits)} visible knowledge hit(s)"
                + (f" within domain '{task.knowledge_domain}'." if task.knowledge_domain else ".")
            )

            repository.update_status(task=task, status=TaskStatus.GENERATING)
            generation_context = self.context_builder.build(
                parsed_input=parsed_input,
                understanding=understanding,
                retrieval_hits=retrieval_hits,
            )
            workflow_result = self._build_workflow_result(
                parsed_input=parsed_input,
                understanding=understanding,
                retrieval_hits=retrieval_hits,
                generation_context=generation_context,
                processing_trace=processing_trace,
            )

            return repository.update_pipeline_results(
                task=task,
                status=TaskStatus.REVIEW_PENDING,
                understanding=understanding,
                retrieval_hits=retrieval_hits,
                workflow_result=workflow_result,
            )

    def _parse_input(self, input_type: str, content: str) -> dict[str, Any]:
        """Normalize the current input into deterministic text plus quality metadata.

        This is intentionally a placeholder implementation. The stable contract
        is that later stages receive a plain-text representation regardless of
        whether the source started as text, URL, or file input.
        """

        source_kind = input_type
        processing_trace: list[str] = []
        input_metadata: dict[str, Any] = {}
        if input_type == "url":
            extracted = self.url_ingestion_service.fetch_public_content(content)
            parsed_text = str(extracted["text"])
            input_metadata = {
                "title": extracted["title"],
                "extractor": extracted["extractor"],
                "quality_flags": list(extracted["quality_flags"]),
            }
            processing_trace.append(
                "Parsed url input into reviewer-usable plain text with extractor metadata."
            )
        elif input_type == "file":
            parsed_text = Path(content).read_text(encoding="utf-8").strip()
            processing_trace.append("Read uploaded file contents into pipeline text.")
        else:
            parsed_text = content.strip()
            processing_trace.append("Normalized raw text input for downstream pipeline stages.")

        quality_flags: list[str] = []
        if len(parsed_text) < 40:
            quality_flags.append("short_input")
        if input_type == "url":
            quality_flags.extend(input_metadata.get("quality_flags", []))

        retrieval_query = self._build_retrieval_query(parsed_text)
        processing_trace.append("Built a retrieval-oriented query from the parsed source content.")

        return {
            "source_kind": source_kind,
            "parsed_text": parsed_text,
            "retrieval_query": retrieval_query,
            "input_quality": {
                "source_kind": source_kind,
                "quality_flags": quality_flags,
                "extracted_length": len(parsed_text),
                "metadata": input_metadata,
            },
            "processing_trace": processing_trace,
        }

    def _build_understanding(self, parsed_input: dict[str, Any]) -> dict[str, Any]:
        """Produce a deterministic structured-understanding payload for Phase 1."""

        parsed_text = parsed_input["parsed_text"]
        input_quality = parsed_input["input_quality"]
        snippet = parsed_text[:80].strip() or "No content provided."
        risk_points: list[str] = []
        uncertain_items: list[str] = []

        quality_flags = input_quality.get("quality_flags", [])
        if "short_input" in quality_flags:
            risk_points.append("Input is very short")
            uncertain_items.append("Source content may be incomplete")
        if "shallow_url_extract" in quality_flags:
            risk_points.append("URL extraction may be shallow or noisy")
            uncertain_items.append("Public page extraction may have missed key article sections")

        return {
            "summary": f"Structured summary for: {snippet}",
            "audience": ["content-ops", "brand"],
            "key_points": [
                "The task requires structured understanding before generation.",
                "References should remain visible to the reviewer.",
                "Human review is required before export.",
            ],
            "risk_points": risk_points or ["Claims still require reviewer verification before export."],
            "uncertain_items": uncertain_items or ["Final business angle still needs human confirmation."],
            "input_quality": input_quality,
        }

    def _build_retrieval_hits(
        self,
        session: Session,
        parsed_text: str,
        *,
        knowledge_domain: str | None,
    ) -> list[dict[str, Any]]:
        """Return reviewer-visible retrieval hits in the stable attribution shape."""

        repository = KnowledgeRepository(session)
        retrieval_service = RetrievalService(repository)
        return retrieval_service.retrieve(parsed_text, top_k=3, domain=knowledge_domain)

    def _build_workflow_result(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        generation_context: dict[str, Any],
        processing_trace: list[str],
    ) -> dict[str, Any]:
        """Assemble the pre-review workflow result shown in the console."""

        evidence_used = [
            {
                "source_id": hit["source_id"],
                "title": hit["title"],
            }
            for hit in generation_context["selected_hits"]
        ]
        manual_checks = [
            "Confirm the final business angle before export.",
            "Verify every externally visible claim against the cited evidence.",
        ]
        if understanding["uncertain_items"]:
            manual_checks.extend(understanding["uncertain_items"])
        if "shallow_url_extract" in parsed_input["input_quality"]["quality_flags"]:
            manual_checks.append("Confirm the source article is complete before approval.")

        context_summary = {
            "selected_hit_count": len(generation_context["selected_hits"]),
            "context_sections": generation_context["sections"],
            "duplicate_hits_removed": generation_context["duplicate_hits_removed"],
        }
        processing_trace = [
            *processing_trace,
            "Assembled a constrained context package before generation.",
            "Generated a reviewer-facing draft that keeps uncertainty visible.",
        ]

        return {
            "draft": (
                "Draft workflow result based on the structured understanding and visible retrieval hits. "
                f"Primary audience: {', '.join(understanding['audience'])}."
            ),
            "review_notes": [
                "Confirm the final business angle before export.",
                (
                    f"Verify the cited sources: {', '.join(hit['source_id'] for hit in retrieval_hits)}."
                    if retrieval_hits
                    else "No indexed knowledge hits were available for this task yet."
                ),
            ],
            "open_questions": [
                "Does the generated angle match the brand constraint?",
                "Are any claims missing manual confirmation?",
            ],
            "evidence_used": evidence_used,
            "uncertainties": understanding["uncertain_items"],
            "manual_checks": manual_checks,
            "context_summary": context_summary,
            "processing_trace": processing_trace,
        }

    def _build_retrieval_query(self, parsed_text: str) -> str:
        """Extract a slightly more retrieval-friendly query from the parsed source."""

        normalized = " ".join(parsed_text.split())
        return normalized[:400]
