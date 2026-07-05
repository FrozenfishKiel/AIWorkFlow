import { apiClient } from "./api";
import type {
  ApiProductContentJobRecord,
  ProductContentAuditLog,
  ProductContentJobDetail,
  ProductInputFormValues,
} from "../types/productContent";
import { splitLines } from "../types/productContent";

function normalizeReferenceItem(item: {
  source_id: string;
  title: string;
  snippet: string;
  reason: string;
  rank?: number | null;
  score?: number | null;
  selected?: boolean;
  matched_terms?: string[];
  matched_phrases?: string[];
  visible_text?: string;
}) {
  return {
    sourceId: item.source_id,
    title: item.title,
    snippet: item.snippet,
    reason: item.reason,
    rank: item.rank ?? null,
    score: item.score ?? null,
    selected: item.selected ?? false,
    matchedTerms: item.matched_terms ?? [],
    matchedPhrases: item.matched_phrases ?? [],
    visibleText: item.visible_text ?? "",
  };
}

function normalizeProductContentJob(record: ApiProductContentJobRecord): ProductContentJobDetail {
  return {
    id: record.id,
    status: record.status,
    currentStage: record.current_stage,
    errorMessage: record.error_message,
    product: {
      name: record.product.name,
      category: record.product.category,
      specifications: record.product.specifications,
      priceRange: record.product.price_range ?? null,
      coreSellingPoints: record.product.core_selling_points,
      targetAudience: record.product.target_audience ?? null,
      useScenarios: record.product.use_scenarios,
      promotionNotes: record.product.promotion_notes ?? null,
    },
    taskDescription: record.task_description,
    productBrief: record.product_brief
      ? {
          summary: record.product_brief.summary,
          targetAudience: record.product_brief.target_audience ?? null,
          useScenarios: record.product_brief.use_scenarios,
          primaryValuePoints: record.product_brief.primary_value_points,
        }
      : null,
    sellingStrategy: record.selling_strategy
      ? {
          primaryAngle: record.selling_strategy.primary_angle,
          supportingAngles: record.selling_strategy.supporting_angles,
          scenarioFocus: record.selling_strategy.scenario_focus,
          expressionGuardrails: record.selling_strategy.expression_guardrails,
        }
      : null,
    inputAlerts: record.input_alerts ?? [],
    referenceContext: record.reference_context.map(normalizeReferenceItem),
    retrievalCandidates: (record.retrieval_candidates ?? []).map(normalizeReferenceItem),
    contextSummary: record.context_summary ?? {},
    diagnostics: record.diagnostics
      ? {
          generationProvider: record.diagnostics.generation_provider ?? "",
          retrievalProvider: record.diagnostics.retrieval_provider ?? "",
          retrievalQuery: record.diagnostics.retrieval_query ?? "",
          retrievalTopKRequested: record.diagnostics.retrieval_top_k_requested ?? 0,
          retrievalTopKEffective: record.diagnostics.retrieval_top_k_effective ?? 0,
          candidateHitCount: record.diagnostics.candidate_hit_count ?? 0,
          selectedHitCount: record.diagnostics.selected_hit_count ?? 0,
          selectedSourceIds: record.diagnostics.selected_source_ids ?? [],
          selectedTitles: record.diagnostics.selected_titles ?? [],
          weakRetrieval: record.diagnostics.weak_retrieval ?? false,
          duplicateHitsRemoved: record.diagnostics.duplicate_hits_removed ?? 0,
          failureStage: record.diagnostics.failure_stage ?? null,
          failureReason: record.diagnostics.failure_reason ?? null,
        }
      : null,
    processingTrace: record.processing_trace ?? [],
    generatedContent: record.generated_content
      ? {
          sellingPointsCopy: record.generated_content.selling_points_copy,
          detailPageCopy: record.generated_content.detail_page_copy,
          socialSeedCopy: record.generated_content.social_seed_copy,
          riskNotes: record.generated_content.risk_notes,
          appliedGuidelines: record.generated_content.applied_guidelines,
        }
      : null,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
  };
}

function toCreatePayload(values: ProductInputFormValues) {
  return {
    product: {
      name: values.name.trim(),
      category: values.category.trim(),
      specifications: splitLines(values.specificationsText),
      price_range: values.priceRange.trim() || null,
      core_selling_points: splitLines(values.coreSellingPointsText),
      target_audience: values.targetAudience.trim() || null,
      use_scenarios: splitLines(values.useScenariosText),
      promotion_notes: values.promotionNotes.trim() || null,
    },
    task_description: values.taskDescription.trim(),
  };
}

export async function createProductContentJob(values: ProductInputFormValues): Promise<string> {
  const response = await apiClient.post<ApiProductContentJobRecord>(
    "/product-content/jobs",
    toCreatePayload(values),
  );
  return response.id;
}

export async function fetchProductContentJob(jobId: string): Promise<ProductContentJobDetail> {
  const response = await apiClient.get<ApiProductContentJobRecord>(`/product-content/jobs/${jobId}`);
  return normalizeProductContentJob(response);
}

export async function fetchProductContentJobAuditLogs(jobId: string): Promise<ProductContentAuditLog[]> {
  const response = await apiClient.get<
    Array<{
      id: string;
      task_id: string;
      export_job_id?: string | null;
      event_type: string;
      outcome: "success" | "failure";
      summary: string;
      details?: Record<string, unknown>;
      created_at: string;
    }>
  >(`/product-content/jobs/${jobId}/audit-logs`);
  return response.map((item) => ({
    id: item.id,
    taskId: item.task_id,
    exportJobId: item.export_job_id ?? null,
    eventType: item.event_type,
    outcome: item.outcome,
    summary: item.summary,
    details: item.details ?? {},
    createdAt: item.created_at,
  }));
}

export { normalizeProductContentJob };
