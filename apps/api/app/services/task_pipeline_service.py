from __future__ import annotations

import json
import re
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
    - real model-backed understanding/workflow generation
    - model-backed retrieval query normalization
    - reviewer-visible retrieval and export snapshot boundaries
    """

    UNSUPPORTED_OUTPUT_PLACEHOLDER_PATTERN = re.compile(
        r"(?:X{2,}|x{2,}|某[a-zA-Z0-9\u4e00-\u9fff]{0,4}|待补充|待确认|TBD|to be confirmed)",
        re.IGNORECASE,
    )
    UNSUPPORTED_NUMERIC_FACT_PATTERN = re.compile(
        r"\d+(?:\.\d+)?\s?(?:g|kg|ml|l|L|条|片|档|分钟|小时|天|次|%|元|℃)",
        re.IGNORECASE,
    )

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
            parsed_input: dict[str, Any] | None = None
            understanding: dict[str, Any] | None = None
            retrieval_hits: list[dict[str, Any]] = []
            retrieval_diagnostics: dict[str, Any] = {}
            generation_context: dict[str, Any] | None = None
            selling_strategy: dict[str, Any] | None = None

            try:
                repository.update_status(task=task, status=TaskStatus.PARSING)
                parsed_input = self._parse_input(task.input_type, task.content)
                processing_trace.extend(parsed_input["processing_trace"])

                repository.update_status(task=task, status=TaskStatus.UNDERSTANDING)
                understanding = self._build_understanding(parsed_input)
                processing_trace.append(
                    f"Built structured understanding with risk and uncertainty markers via {self.generation_provider.provider_name}."
                )

                repository.update_status(task=task, status=TaskStatus.RETRIEVING)
                retrieval_result = self._build_retrieval_hits(
                    session,
                    parsed_input["retrieval_query"],
                    knowledge_domain=task.knowledge_domain,
                )
                retrieval_hits = list(retrieval_result["hits"])
                retrieval_diagnostics = dict(retrieval_result["diagnostics"])
                processing_trace.append(
                    f"Retrieved {len(retrieval_hits)} visible knowledge hit(s)"
                    + (f" within domain '{task.knowledge_domain}'." if task.knowledge_domain else ".")
                )

                generation_context = self.context_builder.build(
                    parsed_input=parsed_input,
                    understanding=understanding,
                    retrieval_hits=retrieval_hits,
                )
                selling_strategy = None
                if parsed_input["source_kind"] == "product_request":
                    selling_strategy = self._build_selling_strategy(
                        parsed_input=parsed_input,
                        understanding=understanding,
                        retrieval_hits=generation_context["selected_hits"],
                    )
                    processing_trace.append("Built the shared selling-strategy layer for the three output channels.")

                repository.update_status(task=task, status=TaskStatus.GENERATING)
                if selling_strategy is not None:
                    generation_context["selling_strategy"] = selling_strategy
                    generation_context["sections"] = [*generation_context["sections"], "selling_strategy"]
                workflow_result = self._build_workflow_result(
                    parsed_input=parsed_input,
                    understanding=understanding,
                    retrieval_hits=retrieval_hits,
                    generation_context=generation_context,
                    retrieval_diagnostics=retrieval_diagnostics,
                    processing_trace=processing_trace,
                    selling_strategy=selling_strategy,
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
            except Exception as exc:
                failure_details = self._build_failure_diagnostics(
                    task=task,
                    parsed_input=parsed_input,
                    retrieval_hits=retrieval_hits,
                    retrieval_diagnostics=retrieval_diagnostics,
                    generation_context=generation_context,
                    processing_trace=processing_trace,
                    error_message=str(exc),
                )
                repository.update_status(
                    task=task,
                    status=TaskStatus.FAILED,
                    error_message=str(exc),
                )
                audit_repository.create_log(
                    task_id=task.id,
                    event_type=AuditEventType.PIPELINE_FAILED,
                    outcome=AuditOutcome.FAILURE,
                    summary="Pipeline failed before a stable result could be persisted.",
                    details=failure_details,
                )
                raise

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

        if input_type == "product_request":
            retrieval_query = self._build_product_request_retrieval_query(
                product_payload=product_payload,
                task_description=task_description,
            )
        else:
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
            product_payload = parsed_input.get("product_payload", {})
            raw_target_audience = str(product_payload.get("target_audience") or "").strip()
            raw_use_scenarios = [
                str(item).strip()
                for item in product_payload.get("use_scenarios", [])
                if str(item).strip()
            ]
            raw_value_points = [
                str(item).strip()
                for item in product_payload.get("core_selling_points", [])
                if str(item).strip()
            ]
            target_audience = str(payload.get("target_audience") or "").strip()
            if not target_audience or self._is_generic_placeholder(target_audience):
                target_audience = raw_target_audience or "未明确目标人群"
            use_scenarios = self._prefer_product_terms(
                payload.get("use_scenarios", []),
                raw_use_scenarios,
            )
            primary_value_points = self._prefer_product_terms(
                payload.get("primary_value_points", []),
                raw_value_points,
            )
            summary = self._stabilize_product_summary(
                str(payload.get("summary") or "").strip(),
                product_payload=product_payload,
                target_audience=target_audience,
                primary_value_points=primary_value_points,
            )
            return {
                **payload,
                "summary": summary,
                "target_audience": target_audience,
                "use_scenarios": use_scenarios,
                "primary_value_points": primary_value_points,
                "input_alerts": self._build_input_alerts(parsed_input),
            }

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
    ) -> dict[str, Any]:
        """Return reviewer-visible retrieval hits in the stable attribution shape."""

        repository = KnowledgeRepository(session)
        retrieval_service = RetrievalService(repository)
        top_k = 4 if knowledge_domain == "ecommerce" else 3
        hits = retrieval_service.retrieve(parsed_text, top_k=top_k, domain=knowledge_domain)
        return {
            "hits": hits,
            "diagnostics": {
                "retrieval_provider": retrieval_service.retrieval_profile_provider.provider_name,
                "retrieval_query": parsed_text,
                "retrieval_top_k_requested": top_k,
                "retrieval_top_k_effective": len(hits),
            },
        }

    def _build_workflow_result(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        generation_context: dict[str, Any],
        retrieval_diagnostics: dict[str, Any],
        processing_trace: list[str],
        selling_strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the workflow result shown in the console and stable snapshot."""

        if parsed_input["source_kind"] == "product_request":
            workflow_core = self.generation_provider.build_workflow(
                parsed_input=parsed_input,
                understanding=understanding,
                retrieval_hits=retrieval_hits,
                generation_context=generation_context,
            )
            workflow_core, sanitization_notes = self._sanitize_product_workflow_output(
                parsed_input=parsed_input,
                workflow_core=workflow_core,
            )
            if self._product_workflow_looks_off_topic(parsed_input, workflow_core):
                raise ValueError(
                    "模型输出偏离商品事实，已终止当前任务，避免用固定保底草稿冒充真实生成结果。"
                )
            selected_evidence = [
                {
                    "source_id": hit["source_id"],
                    "title": hit["title"],
                    "snippet": hit["snippet"],
                    "reason": hit["reason"],
                }
                for hit in generation_context["selected_hits"]
            ]
            retrieval_quality = dict(generation_context.get("retrieval_quality", {}))
            input_alerts = [
                str(item).strip()
                for item in understanding.get("input_alerts", [])
                if str(item).strip()
            ]
            risk_notes = list(workflow_core.get("risk_notes", []))
            if input_alerts:
                risk_notes.append("输入信息仍有缺口，当前结果更适合作为人工补写底稿。")
            if retrieval_quality.get("weak_retrieval", not retrieval_hits):
                risk_notes.append("当前没有命中足够具体的商品或类目事实资料，建议补充商品事实卡或类目资料后再复核。")
            risk_notes.extend(sanitization_notes)
            workflow_core["applied_guidelines"] = self._dedupe_preserve_order(
                list(workflow_core.get("applied_guidelines", []))
            )
            workflow_core["risk_notes"] = self._dedupe_preserve_order(risk_notes)
            workflow_core["selling_strategy"] = selling_strategy or self._build_selling_strategy(
                parsed_input=parsed_input,
                understanding=understanding,
                retrieval_hits=generation_context["selected_hits"],
            )
            workflow_core["evidence_used"] = selected_evidence
            workflow_core["context_summary"] = {
                "candidate_hit_count": len(retrieval_hits),
                "selected_hit_count": len(selected_evidence),
                "weak_retrieval": bool(retrieval_quality.get("weak_retrieval", not selected_evidence)),
                "duplicate_hits_removed": generation_context["duplicate_hits_removed"],
            }
            workflow_core["diagnostics"] = self._build_runtime_diagnostics(
                parsed_input=parsed_input,
                retrieval_hits=retrieval_hits,
                generation_context=generation_context,
                retrieval_diagnostics=retrieval_diagnostics,
                failure_reason=None,
            )
            workflow_core["processing_trace"] = [
                *processing_trace,
                "Assembled a constrained product-content context package before generation.",
                f"Passed retrieval quality state into generation via {self.generation_provider.provider_name}.",
            ]
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
            "diagnostics": self._build_runtime_diagnostics(
                parsed_input=parsed_input,
                retrieval_hits=retrieval_hits,
                generation_context=generation_context,
                retrieval_diagnostics=retrieval_diagnostics,
                failure_reason=None,
            ),
            "processing_trace": processing_trace,
        }

    def _build_retrieval_query(self, parsed_text: str) -> str:
        """Extract a slightly more retrieval-friendly query from the parsed source."""

        normalized = " ".join(parsed_text.split())
        return normalized[:400]

    def _build_product_request_retrieval_query(
        self,
        *,
        product_payload: dict[str, Any],
        task_description: str,
    ) -> str:
        product_name = str(product_payload.get("name") or "").strip()
        category = str(product_payload.get("category") or "").strip()
        selling_points = [
            str(item).strip()
            for item in product_payload.get("core_selling_points", [])
            if str(item).strip()
        ][:3]
        target_audience = str(product_payload.get("target_audience") or "").strip()
        scenarios = [
            str(item).strip()
            for item in product_payload.get("use_scenarios", [])
            if str(item).strip()
        ][:3]

        sections: list[str] = []
        if product_name:
            sections.append(f"商品 {product_name}")
        if category:
            sections.append(f"类目 {category}")
        if selling_points:
            sections.append(f"核心卖点 {' '.join(selling_points)}")
        if target_audience:
            sections.append(f"目标人群 {target_audience}")
        if scenarios:
            sections.append(f"使用场景 {' '.join(scenarios)}")

        task_targets = self._dedupe_preserve_order(self._extract_task_goal_signals(task_description))
        if any(marker in task_description for marker in ("真实使用感", "真实体验", "使用感", "不要太广告", "广告感")):
            for item in ("真实体验", "使用感", "场景感"):
                if item not in task_targets:
                    task_targets.append(item)
        if task_targets:
            sections.append(f"内容目标 {' '.join(task_targets)}")

        return "\n".join(sections)

    def _extract_task_goal_signals(self, task_description: str) -> list[str]:
        normalized = " ".join(task_description.split())
        goal_markers = (
            "小红书",
            "种草",
            "详情页",
            "卖点",
            "直播",
            "短视频",
            "主图",
            "标题",
        )
        return [
            marker
            for marker in goal_markers
            if marker in normalized
        ]

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

    def _build_input_alerts(self, parsed_input: dict[str, Any]) -> list[str]:
        product_payload = parsed_input.get("product_payload", {})
        alerts: list[str] = []

        specifications = [str(item).strip() for item in product_payload.get("specifications", []) if str(item).strip()]
        selling_points = [str(item).strip() for item in product_payload.get("core_selling_points", []) if str(item).strip()]
        use_scenarios = [str(item).strip() for item in product_payload.get("use_scenarios", []) if str(item).strip()]
        target_audience = str(product_payload.get("target_audience") or "").strip()

        if len(specifications) < 2:
            alerts.append("规格参数还可以补充更细。")
        if len(selling_points) < 2:
            alerts.append("核心卖点信息偏少，建议补充至少两个明确卖点。")
        if not target_audience:
            alerts.append("目标人群信息较弱，建议补充更具体的使用对象。")
        if not use_scenarios:
            alerts.append("使用场景信息较弱，建议补充典型使用场景。")

        return self._dedupe_preserve_order(alerts)

    def _build_selling_strategy(
        self,
        *,
        parsed_input: dict[str, Any],
        understanding: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        product_payload = parsed_input.get("product_payload", {})
        value_points = self._prefer_product_terms(
            understanding.get("primary_value_points", []),
            [
                str(item).strip()
                for item in product_payload.get("core_selling_points", [])
                if str(item).strip()
            ],
        )
        scenario_focus = self._prefer_product_terms(
            understanding.get("use_scenarios", []),
            [
                str(item).strip()
                for item in product_payload.get("use_scenarios", [])
                if str(item).strip()
            ],
        )
        guardrails: list[str] = []
        for hit in retrieval_hits:
            note = self._format_guardrail_note(hit)
            if note:
                guardrails.append(note)
        if not guardrails:
            guardrails.append("优先保持真实体验表达，避免绝对化承诺。")

        primary_angle = value_points[0] if value_points else str(understanding.get("summary") or "").strip()
        supporting_angles = value_points[1:3]

        return {
            "primary_angle": primary_angle,
            "supporting_angles": supporting_angles,
            "scenario_focus": scenario_focus,
            "expression_guardrails": self._dedupe_preserve_order(guardrails),
        }

    def _format_guardrail_note(self, hit: dict[str, Any]) -> str:
        """Turn one selected evidence item into a human-readable expression guardrail."""

        title = str(hit.get("title") or "").strip()
        snippet = " ".join(str(hit.get("snippet") or "").split()).strip()
        if not title and not snippet:
            return ""
        if snippet:
            return f"参考《{title}》：{snippet[:48]}"
        return f"参考《{title}》调整表达边界。"

    def _prefer_product_terms(self, generated_terms: list[Any], raw_terms: list[str]) -> list[str]:
        """Prefer concrete user input over generic model placeholders."""

        cleaned_generated = [
            str(item).strip()
            for item in generated_terms
            if str(item).strip() and not self._is_generic_placeholder(str(item))
        ]
        return cleaned_generated or raw_terms

    def _stabilize_product_summary(
        self,
        generated_summary: str,
        *,
        product_payload: dict[str, Any],
        target_audience: str,
        primary_value_points: list[str],
    ) -> str:
        """Keep the product brief anchored to explicit user facts."""

        product_name = str(product_payload.get("name") or "该商品").strip() or "该商品"
        category = str(product_payload.get("category") or "").strip()
        if generated_summary and product_name in generated_summary:
            return generated_summary

        summary_parts = [product_name]
        if category:
            summary_parts.append(f"是一款{category}产品")
        if target_audience and "未明确" not in target_audience:
            summary_parts.append(f"面向{target_audience}")
        if primary_value_points:
            summary_parts.append(f"重点突出{'、'.join(primary_value_points[:3])}")
        return "，".join(summary_parts) + "。"

    def _sanitize_product_workflow_output(
        self,
        *,
        parsed_input: dict[str, Any],
        workflow_core: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        product_payload = dict(parsed_input.get("product_payload") or {})
        allowed_text = "\n".join(
            [
                str(product_payload.get("name") or ""),
                str(product_payload.get("category") or ""),
                str(product_payload.get("price_range") or ""),
                str(product_payload.get("target_audience") or ""),
                str(product_payload.get("promotion_notes") or ""),
                *[str(item) for item in product_payload.get("specifications", [])],
                *[str(item) for item in product_payload.get("core_selling_points", [])],
                *[str(item) for item in product_payload.get("use_scenarios", [])],
            ]
        )
        notes: list[str] = []

        selling_points = [
            str(item).strip()
            for item in workflow_core.get("selling_points_copy", [])
            if str(item).strip()
        ]
        sanitized_points = [
            item
            for item in selling_points
            if not self._contains_unsupported_output_placeholder(item, allowed_text=allowed_text)
        ]
        if len(sanitized_points) != len(selling_points):
            notes.append("已移除提及占位表达或未获支持具体数值的卖点，请补充实物规格后复核。")
        workflow_core["selling_points_copy"] = sanitized_points

        detail_page_copy, detail_changed = self._strip_placeholder_sentences(
            str(workflow_core.get("detail_page_copy") or "").strip(),
            allowed_text=allowed_text,
        )
        social_seed_copy, social_changed = self._strip_placeholder_sentences(
            str(workflow_core.get("social_seed_copy") or "").strip(),
            allowed_text=allowed_text,
        )
        if detail_changed or social_changed:
            notes.append("已自动删去包含占位或未获支持事实的句子，当前文案请按真实商品信息再复核。")
        workflow_core["detail_page_copy"] = detail_page_copy
        workflow_core["social_seed_copy"] = social_seed_copy

        return workflow_core, self._dedupe_preserve_order(notes)

    def _strip_placeholder_sentences(
        self,
        text: str,
        *,
        allowed_text: str,
    ) -> tuple[str, bool]:
        if not text:
            return "", False

        segments = re.split(r"([。！？!?])", text)
        rebuilt: list[str] = []
        changed = False
        for index in range(0, len(segments), 2):
            sentence = segments[index].strip()
            punctuation = segments[index + 1] if index + 1 < len(segments) else ""
            if not sentence:
                continue
            if self._contains_unsupported_output_placeholder(sentence, allowed_text=allowed_text):
                changed = True
                continue
            rebuilt.append(f"{sentence}{punctuation}".strip())

        sanitized = " ".join(part for part in rebuilt if part).strip()
        return sanitized or text, changed

    def _contains_unsupported_output_placeholder(self, text: str, *, allowed_text: str) -> bool:
        for match in self.UNSUPPORTED_OUTPUT_PLACEHOLDER_PATTERN.finditer(text):
            if match.group(0) and match.group(0) in allowed_text:
                continue
            return True
        normalized_allowed = allowed_text.replace(" ", "")
        for match in self.UNSUPPORTED_NUMERIC_FACT_PATTERN.finditer(text):
            candidate = match.group(0).replace(" ", "")
            if candidate and candidate in normalized_allowed:
                continue
            return True
        return False

    def _is_generic_placeholder(self, value: str) -> bool:
        normalized = value.strip()
        if not normalized:
            return True

        generic_markers = (
            "未明确",
            "不明确",
            "待补充",
            "需进一步补充",
            "信息不足",
            "未知",
            "潜在消费者",
        )
        return any(marker in normalized for marker in generic_markers)

    def _product_workflow_looks_off_topic(
        self,
        parsed_input: dict[str, Any],
        workflow_core: dict[str, Any],
    ) -> bool:
        """Detect obviously off-topic model output before it reaches the user."""

        output_parts = [
            *[str(item).strip() for item in workflow_core.get("selling_points_copy", []) if str(item).strip()],
            str(workflow_core.get("detail_page_copy") or "").strip(),
            str(workflow_core.get("social_seed_copy") or "").strip(),
        ]
        output_text = " ".join(part for part in output_parts if part)
        if not output_text:
            return True

        ascii_letters = sum(1 for character in output_text if character.isascii() and character.isalpha())
        cjk_characters = sum(1 for character in output_text if "\u4e00" <= character <= "\u9fff")
        if ascii_letters > 20 and cjk_characters == 0:
            return True

        product_payload = parsed_input.get("product_payload", {})
        factual_anchors = [
            str(product_payload.get("name") or "").strip(),
            str(product_payload.get("category") or "").strip(),
            *[str(item).strip() for item in product_payload.get("specifications", []) if str(item).strip()],
            str(product_payload.get("target_audience") or "").strip(),
            *[str(item).strip() for item in product_payload.get("core_selling_points", []) if str(item).strip()],
            *[str(item).strip() for item in product_payload.get("use_scenarios", []) if str(item).strip()],
        ]
        factual_anchors = [anchor for anchor in factual_anchors if anchor]
        if not factual_anchors:
            return False

        matched_anchor_count = sum(1 for anchor in factual_anchors if anchor and anchor in output_text)
        return matched_anchor_count == 0

    def _build_runtime_diagnostics(
        self,
        *,
        parsed_input: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        generation_context: dict[str, Any],
        retrieval_diagnostics: dict[str, Any],
        failure_reason: str | None,
    ) -> dict[str, Any]:
        selected_hits = generation_context.get("selected_hits", [])
        retrieval_quality = dict(generation_context.get("retrieval_quality", {}))
        return {
            "generation_provider": self.generation_provider.provider_name,
            "retrieval_provider": str(retrieval_diagnostics.get("retrieval_provider") or ""),
            "retrieval_query": str(parsed_input.get("retrieval_query") or ""),
            "retrieval_top_k_requested": int(retrieval_diagnostics.get("retrieval_top_k_requested") or 0),
            "retrieval_top_k_effective": int(retrieval_diagnostics.get("retrieval_top_k_effective") or len(retrieval_hits)),
            "candidate_hit_count": len(retrieval_hits),
            "selected_hit_count": len(selected_hits),
            "selected_source_ids": [
                str(hit.get("source_id") or "").strip()
                for hit in selected_hits
                if str(hit.get("source_id") or "").strip()
            ],
            "selected_titles": [
                str(hit.get("title") or "").strip()
                for hit in selected_hits
                if str(hit.get("title") or "").strip()
            ],
            "weak_retrieval": bool(retrieval_quality.get("weak_retrieval", not selected_hits)),
            "duplicate_hits_removed": int(generation_context.get("duplicate_hits_removed") or 0),
            "failure_stage": None,
            "failure_reason": failure_reason,
        }

    def _build_failure_diagnostics(
        self,
        *,
        task: Task,
        parsed_input: dict[str, Any] | None,
        retrieval_hits: list[dict[str, Any]],
        retrieval_diagnostics: dict[str, Any],
        generation_context: dict[str, Any] | None,
        processing_trace: list[str],
        error_message: str,
    ) -> dict[str, Any]:
        diagnostics = self._build_runtime_diagnostics(
            parsed_input=parsed_input or {"retrieval_query": ""},
            retrieval_hits=retrieval_hits,
            generation_context=generation_context or {"selected_hits": [], "retrieval_quality": {}, "duplicate_hits_removed": 0},
            retrieval_diagnostics=retrieval_diagnostics,
            failure_reason=error_message,
        )
        diagnostics["failure_stage"] = task.current_stage
        diagnostics["processing_trace"] = list(processing_trace)
        return diagnostics

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
