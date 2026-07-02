from __future__ import annotations

import json
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from uuid import UUID

from docx import Document
from pypdf import PdfReader
from sqlmodel import Session

from app.models import AuditEventType, AuditOutcome, Task, TaskStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.task_repository import TaskRepository
from app.services.generation_provider import (
    TaskGenerationProvider,
    build_task_generation_provider,
)
from app.services.retrieval_service import RetrievalService
from app.services.url_ingestion_service import UrlIngestionService
from app.workflows.context_builder import ContextBuilder


class TaskPipelineService:
    """Runs the current production-facing task pipeline for one async task.

    The chain now uses:
    - real model-backed understanding/workflow generation when configured
    - deterministic fallbacks for tests and offline development
    - reviewer-visible retrieval and export snapshot boundaries
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        generation_provider: TaskGenerationProvider | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.url_ingestion_service = UrlIngestionService()
        self.context_builder = ContextBuilder()
        self.generation_provider = generation_provider or build_task_generation_provider()

    def run_pipeline(self, task_id: str | UUID) -> Task:
        """Execute the pipeline one stage at a time and persist each state change.

        Persisting state before each synthetic stage keeps the polling UI and the
        failure path honest, instead of pretending the whole task is one opaque
        background step.
        """

        with self.session_factory() as session:
            repository = TaskRepository(session)
            audit_repository = AuditLogRepository(session)
            task = repository.require_task(task_id)
            processing_trace: list[str] = []

            repository.update_status(task=task, status=TaskStatus.PARSING)
            parsed_input = self._parse_input(task.input_type, task.content)
            processing_trace.extend(parsed_input["processing_trace"])

            repository.update_status(task=task, status=TaskStatus.UNDERSTANDING)
            understanding = self._build_understanding(parsed_input)
            processing_trace.append(
                f"Built structured understanding with risk and uncertainty markers via {self.generation_provider.provider_name}."
            )

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

            processed_task = repository.update_pipeline_results(
                task=task,
                status=TaskStatus.COMPLETED,
                understanding=understanding,
                retrieval_hits=retrieval_hits,
                workflow_result=workflow_result,
            )
            audit_repository.create_log(
                task_id=processed_task.id,
                event_type=AuditEventType.PIPELINE_COMPLETED,
                outcome=AuditOutcome.SUCCESS,
                summary="Pipeline completed successfully.",
                details={
                    "current_stage": processed_task.current_stage,
                    "selected_hit_count": len(retrieval_hits),
                },
            )
            audit_repository.create_log(
                task_id=processed_task.id,
                event_type=AuditEventType.SNAPSHOT_PERSISTED,
                outcome=AuditOutcome.SUCCESS,
                summary="Stable snapshot persisted for downstream export.",
                details={
                    "snapshot_fields": ["understanding", "retrieval_hits", "workflow_result"],
                },
            )
            # The service returns the task after the session closes, so refresh
            # once more after the audit writes and detach it with loaded fields.
            session.refresh(processed_task)
            session.expunge(processed_task)
            return processed_task

    def _parse_input(self, input_type: str, content: str) -> dict[str, Any]:
        """Normalize the current input into deterministic text plus quality metadata.

        The stable contract is that later stages receive a plain-text
        representation regardless of whether the source started as text, URL,
        or file input.
        """

        source_kind = input_type
        processing_trace: list[str] = []
        input_metadata: dict[str, Any] = {}
        if input_type == "product_request":
            payload = json.loads(content)
            product_payload = payload["product"]
            task_description = str(payload["task_description"]).strip()
            parsed_text = self._build_product_request_text(product_payload, task_description)
            input_metadata = {
                "product_name": product_payload.get("name"),
                "category": product_payload.get("category"),
            }
            processing_trace.append("Normalized structured product request into retrieval-friendly text.")
        elif input_type == "url":
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
            parsed_text = self._read_uploaded_file_text(Path(content))
            processing_trace.append("Parsed uploaded file contents into pipeline text.")
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

        parsed_input = {
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
        if input_type == "product_request":
            parsed_input["product_payload"] = product_payload
            parsed_input["task_description"] = task_description
        return parsed_input

    def _read_uploaded_file_text(self, path: Path) -> str:
        """Return reviewer-visible text for the currently supported file formats."""

        extension = path.suffix.lower()
        if extension in {".txt", ".md"}:
            return path.read_text(encoding="utf-8").strip()
        if extension == ".html":
            return self._extract_html_text(path.read_text(encoding="utf-8")).strip()
        if extension == ".docx":
            document = Document(path)
            return "\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()).strip()
        if extension == ".pdf":
            reader = PdfReader(path)
            return "\n".join((page.extract_text() or "").strip() for page in reader.pages if (page.extract_text() or "").strip()).strip()
        return path.read_text(encoding="utf-8").strip()

    def _extract_html_text(self, raw_html: str) -> str:
        """Strip HTML tags into a minimal plain-text representation."""

        parser = _VisibleTextHtmlParser()
        parser.feed(raw_html)
        parser.close()
        return parser.get_text()

    def _build_understanding(self, parsed_input: dict[str, Any]) -> dict[str, Any]:
        """Produce the structured-understanding payload and retain parser-owned quality signals."""

        payload = self.generation_provider.build_understanding(parsed_input)
        if parsed_input["source_kind"] == "product_request":
            return payload

        input_quality = parsed_input["input_quality"]
        quality_flags = input_quality.get("quality_flags", [])
        risk_points = list(payload.get("risk_points", []))
        uncertain_items = list(payload.get("uncertain_items", []))
        if "short_input" in quality_flags:
            risk_points.append("Input is very short")
            uncertain_items.append("Source content may be incomplete")
        if "shallow_url_extract" in quality_flags:
            risk_points.append("URL extraction may be shallow or noisy")
            uncertain_items.append("Public page extraction may have missed key article sections")

        return {
            **payload,
            "risk_points": self._dedupe_preserve_order(risk_points),
            "uncertain_items": self._dedupe_preserve_order(uncertain_items),
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
        """Assemble the workflow result shown in the console and stable snapshot."""

        if parsed_input["source_kind"] == "product_request":
            workflow_core = self.generation_provider.build_workflow(
                parsed_input=parsed_input,
                understanding=understanding,
                retrieval_hits=retrieval_hits,
                generation_context=generation_context,
            )
            workflow_core["applied_guidelines"] = self._dedupe_preserve_order(
                list(workflow_core.get("applied_guidelines", []))
            )
            workflow_core["risk_notes"] = self._dedupe_preserve_order(
                list(workflow_core.get("risk_notes", []))
            )
            return workflow_core

        workflow_core = self.generation_provider.build_workflow(
            parsed_input=parsed_input,
            understanding=understanding,
            retrieval_hits=retrieval_hits,
            generation_context=generation_context,
        )
        evidence_used = [
            {
                "source_id": hit["source_id"],
                "title": hit["title"],
                "snippet": hit["snippet"],
                "reason": hit["reason"],
            }
            for hit in generation_context["selected_hits"]
        ]
        manual_checks = list(workflow_core.get("manual_checks", []))
        manual_checks.extend(understanding["uncertain_items"])
        if "shallow_url_extract" in parsed_input["input_quality"]["quality_flags"]:
            manual_checks.append("Confirm the source article is complete before reuse.")

        context_summary = {
            "selected_hit_count": len(generation_context["selected_hits"]),
            "context_sections": generation_context["sections"],
            "duplicate_hits_removed": generation_context["duplicate_hits_removed"],
        }
        processing_trace = [
            *processing_trace,
            "Assembled a constrained context package before generation.",
            f"Generated a reviewer-facing draft that keeps uncertainty visible via {self.generation_provider.provider_name}.",
        ]

        return {
            "draft": workflow_core["draft"],
            "review_notes": workflow_core.get("review_notes", []),
            "open_questions": workflow_core.get("open_questions", []),
            "evidence_used": evidence_used,
            "uncertainties": understanding["uncertain_items"],
            "manual_checks": self._dedupe_preserve_order(manual_checks),
            "context_summary": context_summary,
            "processing_trace": processing_trace,
        }

    def _build_retrieval_query(self, parsed_text: str) -> str:
        """Extract a slightly more retrieval-friendly query from the parsed source."""

        normalized = " ".join(parsed_text.split())
        return normalized[:400]

    def _build_product_request_text(self, product_payload: dict[str, Any], task_description: str) -> str:
        sections = [
            f"商品名称：{product_payload.get('name', '')}",
            f"商品类目：{product_payload.get('category', '')}",
            f"规格参数：{'、'.join(product_payload.get('specifications', []))}",
            f"价格带：{product_payload.get('price_range', '')}",
            f"核心卖点：{'、'.join(product_payload.get('core_selling_points', []))}",
            f"目标人群：{product_payload.get('target_audience', '')}",
            f"使用场景：{'、'.join(product_payload.get('use_scenarios', []))}",
            f"活动信息：{product_payload.get('promotion_notes', '')}",
            f"任务描述：{task_description}",
        ]
        return "\n".join(section for section in sections if section.split("：", 1)[1].strip())

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        """Keep reviewer-visible lists stable while avoiding duplicated messages."""

        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped


class _VisibleTextHtmlParser(HTMLParser):
    """Collects visible HTML text into a compact whitespace-normalized string."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self._parts.append(cleaned)

    def get_text(self) -> str:
        return "\n".join(self._parts)
