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
    reference_context: list[ReferenceContextRead] = Field(default_factory=list)
    generated_content: GeneratedContentRead | None = None
    created_at: datetime
    updated_at: datetime
