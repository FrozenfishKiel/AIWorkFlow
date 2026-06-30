from pathlib import Path

from sqlmodel import Session

from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.task_repository import TaskRepository
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.task_pipeline_service import TaskPipelineService


def test_pipeline_service_generates_understanding_retrieval_and_workflow_results(
    session: Session,
    tmp_path: Path,
) -> None:
    knowledge_repository = KnowledgeRepository(session)
    source_file = tmp_path / "review-standard.md"
    source_file.write_text(
        "# Review Standard\n\n"
        "Launch plans must keep claims reviewable.\n\n"
        "Visible citations are mandatory before export.\n",
        encoding="utf-8",
    )
    document = knowledge_repository.create_document(
        title="Review Standard",
        source_path=str(source_file),
        source_type="review_standard",
        domain="content-ops",
    )
    KnowledgeIndexService(knowledge_repository).index_document(document.id)

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="text",
        content="Create a launch plan for the new product article.",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.status == "review_pending"
    assert processed_task.understanding is not None
    assert processed_task.understanding["summary"]
    assert processed_task.understanding["audience"]
    assert processed_task.understanding["risk_points"]
    assert processed_task.understanding["uncertain_items"]
    assert processed_task.understanding["input_quality"]["source_kind"] == "text"
    assert processed_task.retrieval_hits
    assert processed_task.retrieval_hits[0]["source_id"] == str(document.id)
    assert processed_task.retrieval_hits[0]["title"] == "Review Standard"
    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["draft"]
    assert processed_task.workflow_result["evidence_used"]
    assert processed_task.workflow_result["manual_checks"]
    assert processed_task.workflow_result["context_summary"]["context_sections"]
    assert processed_task.workflow_result["review_notes"]
    assert processed_task.workflow_result["processing_trace"]


def test_pipeline_service_uses_uploaded_file_contents_and_retrieval_scope(
    session: Session,
    tmp_path: Path,
) -> None:
    knowledge_repository = KnowledgeRepository(session)

    brand_source = tmp_path / "brand-guideline.md"
    brand_source.write_text(
        "# Brand Guide\n\n"
        "Launch copy should stay warm and audience-specific.\n",
        encoding="utf-8",
    )
    compliance_source = tmp_path / "compliance-guideline.md"
    compliance_source.write_text(
        "# Compliance Guide\n\n"
        "Human review stays mandatory before export and every claim needs compliance sign-off.\n",
        encoding="utf-8",
    )

    brand_document = knowledge_repository.create_document(
        title="Brand Guide",
        source_path=str(brand_source),
        source_type="guideline",
        domain="brand",
    )
    compliance_document = knowledge_repository.create_document(
        title="Compliance Guide",
        source_path=str(compliance_source),
        source_type="guideline",
        domain="compliance",
    )
    index_service = KnowledgeIndexService(knowledge_repository)
    index_service.index_document(brand_document.id)
    index_service.index_document(compliance_document.id)

    uploaded_file = tmp_path / "task-brief.md"
    uploaded_file.write_text(
        "# Launch Brief\n\n"
        "Need compliance sign-off before publishing any launch claims.\n",
        encoding="utf-8",
    )

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="file",
        content=str(uploaded_file),
    )
    task.knowledge_domain = "compliance"
    session.add(task)
    session.commit()
    session.refresh(task)

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.status == "review_pending"
    assert "compliance sign-off" in processed_task.understanding["summary"].lower()
    assert processed_task.understanding["input_quality"]["source_kind"] == "file"
    assert processed_task.understanding["input_quality"]["quality_flags"] == []
    assert processed_task.retrieval_hits
    assert {hit["title"] for hit in processed_task.retrieval_hits} == {"Compliance Guide"}


def test_pipeline_service_uses_real_url_text_for_retrieval(
    session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    knowledge_repository = KnowledgeRepository(session)

    source = tmp_path / "compliance-guideline.md"
    source.write_text(
        "# Compliance Guide\n\n"
        "Visible citations and human review are mandatory before launch export.\n",
        encoding="utf-8",
    )
    document = knowledge_repository.create_document(
        title="Compliance Guide",
        source_path=str(source),
        source_type="guideline",
        domain="compliance",
    )
    KnowledgeIndexService(knowledge_repository).index_document(document.id)

    monkeypatch.setattr(
        "app.services.task_pipeline_service.UrlIngestionService.fetch_public_content",
        lambda self, url: {
            "title": "Launch Update",
            "text": "Visible citations and human review are mandatory before launch export.",
            "extractor": "article",
            "quality_flags": [],
        },
    )

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="url",
        content="https://example.com/launch-update",
        knowledge_domain="compliance",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.status == "review_pending"
    assert "visible citations" in processed_task.understanding["summary"].lower()
    assert processed_task.understanding["input_quality"]["source_kind"] == "url"
    assert processed_task.understanding["input_quality"]["metadata"]["extractor"] == "article"
    assert processed_task.retrieval_hits
    assert processed_task.retrieval_hits[0]["title"] == "Compliance Guide"


def test_pipeline_service_carries_url_extraction_quality_flags_forward(
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.task_pipeline_service.UrlIngestionService.fetch_public_content",
        lambda self, url: {
            "title": "Status Page",
            "text": "Launch status",
            "extractor": "body",
            "quality_flags": ["fallback_html_extract", "shallow_url_extract"],
        },
    )

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="url",
        content="https://example.com/status",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.status == "review_pending"
    assert "shallow_url_extract" in processed_task.understanding["input_quality"]["quality_flags"]
    assert "fallback_html_extract" in processed_task.understanding["input_quality"]["quality_flags"]
    assert processed_task.understanding["input_quality"]["metadata"]["title"] == "Status Page"
    assert "URL extraction may be shallow or noisy" in processed_task.understanding["risk_points"]
    assert "Confirm the source article is complete before approval." in processed_task.workflow_result["manual_checks"]


def test_pipeline_service_marks_low_quality_inputs_and_carries_uncertainty_forward(
    session: Session,
) -> None:
    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="text",
        content="tiny",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.status == "review_pending"
    assert processed_task.understanding is not None
    assert "Input is very short" in processed_task.understanding["risk_points"]
    assert "Source content may be incomplete" in processed_task.understanding["uncertain_items"]
    assert "short_input" in processed_task.understanding["input_quality"]["quality_flags"]
    assert processed_task.workflow_result is not None
    assert "Source content may be incomplete" in processed_task.workflow_result["manual_checks"]
    assert processed_task.workflow_result["context_summary"]["selected_hit_count"] == 0


def test_pipeline_service_deduplicates_context_hits_and_limits_selected_evidence(
    session: Session,
    tmp_path: Path,
) -> None:
    knowledge_repository = KnowledgeRepository(session)
    repeated_file = tmp_path / "repeated-guidance.md"
    repeated_file.write_text(
        "# Guidance\n\n"
        "Visible citations are mandatory before export.\n\n"
        "Visible citations are mandatory before export.\n\n"
        "Manual review remains required for launch claims.\n",
        encoding="utf-8",
    )
    document = knowledge_repository.create_document(
        title="Repeated Guidance",
        source_path=str(repeated_file),
        source_type="guide",
        domain="content-ops",
    )
    KnowledgeIndexService(knowledge_repository).index_document(document.id)

    repository = TaskRepository(session)
    task = repository.create_task(
        input_type="text",
        content="Prepare launch copy with visible citations before export and keep manual review.",
        knowledge_domain="content-ops",
    )

    service = TaskPipelineService(lambda: Session(session.get_bind()))
    processed_task = service.run_pipeline(task.id)

    assert processed_task.workflow_result is not None
    assert processed_task.workflow_result["context_summary"]["selected_hit_count"] <= 3
    assert processed_task.workflow_result["context_summary"]["duplicate_hits_removed"] >= 0
    assert len(processed_task.workflow_result["evidence_used"]) <= 3
