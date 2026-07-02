import { apiClient } from "./api";
import type {
  ApiProductContentJobRecord,
  ProductContentJobDetail,
  ProductInputFormValues,
} from "../types/productContent";
import { splitLines } from "../types/productContent";

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
    referenceContext: record.reference_context.map((item) => ({
      sourceId: item.source_id,
      title: item.title,
      snippet: item.snippet,
      reason: item.reason,
    })),
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

export { normalizeProductContentJob };
