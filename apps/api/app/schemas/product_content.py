from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import TaskStatus


class ProductInput(BaseModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    specifications: list[str] = Field(default_factory=list)
    price_range: str | None = None
    core_selling_points: list[str] = Field(default_factory=list)
    target_audience: str | None = None
    use_scenarios: list[str] = Field(default_factory=list)
    promotion_notes: str | None = None


class ProductContentJobCreateRequest(BaseModel):
    product: ProductInput
    task_description: str = Field(min_length=1)


class ProductBriefRead(BaseModel):
    summary: str
    target_audience: str | None = None
    use_scenarios: list[str] = Field(default_factory=list)
    primary_value_points: list[str] = Field(default_factory=list)


class ReferenceContextRead(BaseModel):
    source_id: str
    title: str
    snippet: str
    reason: str
    rank: int | None = None
    score: float | None = None
    selected: bool = False
    matched_terms: list[str] = Field(default_factory=list)
    matched_phrases: list[str] = Field(default_factory=list)
    visible_text: str = ""


class ProductContentDiagnosticsRead(BaseModel):
    generation_provider: str = ""
    retrieval_provider: str = ""
    retrieval_query: str = ""
    retrieval_top_k_requested: int = 0
    retrieval_top_k_effective: int = 0
    candidate_hit_count: int = 0
    selected_hit_count: int = 0
    selected_source_ids: list[str] = Field(default_factory=list)
    selected_titles: list[str] = Field(default_factory=list)
    weak_retrieval: bool = False
    duplicate_hits_removed: int = 0
    failure_stage: str | None = None
    failure_reason: str | None = None


class SellingStrategyRead(BaseModel):
    primary_angle: str = ""
    supporting_angles: list[str] = Field(default_factory=list)
    scenario_focus: list[str] = Field(default_factory=list)
    expression_guardrails: list[str] = Field(default_factory=list)


class GeneratedContentRead(BaseModel):
    selling_points_copy: list[str] = Field(default_factory=list)
    detail_page_copy: str = ""
    social_seed_copy: str = ""
    risk_notes: list[str] = Field(default_factory=list)
    applied_guidelines: list[str] = Field(default_factory=list)


class ProductContentJobRead(BaseModel):
    id: UUID
    status: TaskStatus
    current_stage: str
    error_message: str | None = None
    product: ProductInput
    task_description: str
    product_brief: ProductBriefRead | None = None
    selling_strategy: SellingStrategyRead | None = None
    input_alerts: list[str] = Field(default_factory=list)
    reference_context: list[ReferenceContextRead] = Field(default_factory=list)
    retrieval_candidates: list[ReferenceContextRead] = Field(default_factory=list)
    context_summary: dict[str, object] = Field(default_factory=dict)
    diagnostics: ProductContentDiagnosticsRead | None = None
    processing_trace: list[str] = Field(default_factory=list)
    generated_content: GeneratedContentRead | None = None
    created_at: datetime
    updated_at: datetime
