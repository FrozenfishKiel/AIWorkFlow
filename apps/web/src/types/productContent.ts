export type ProductContentJobStatus =
  | "queued"
  | "parsing"
  | "understanding"
  | "retrieving"
  | "generating"
  | "exporting"
  | "completed"
  | "failed";

export interface ProductInputFormValues {
  name: string;
  category: string;
  specificationsText: string;
  priceRange: string;
  coreSellingPointsText: string;
  targetAudience: string;
  useScenariosText: string;
  promotionNotes: string;
  taskDescription: string;
}

export interface ProductInput {
  name: string;
  category: string;
  specifications: string[];
  priceRange: string | null;
  coreSellingPoints: string[];
  targetAudience: string | null;
  useScenarios: string[];
  promotionNotes: string | null;
}

export interface ProductBrief {
  summary: string;
  targetAudience: string | null;
  useScenarios: string[];
  primaryValuePoints: string[];
}

export interface SellingStrategy {
  primaryAngle: string;
  supportingAngles: string[];
  scenarioFocus: string[];
  expressionGuardrails: string[];
}

export interface ReferenceContextItem {
  sourceId: string;
  title: string;
  snippet: string;
  reason: string;
  rank?: number | null;
  score?: number | null;
  selected?: boolean;
  matchedTerms?: string[];
  matchedPhrases?: string[];
  visibleText?: string;
}

export interface ProductContentDiagnostics {
  generationProvider: string;
  retrievalProvider: string;
  retrievalQuery: string;
  retrievalTopKRequested: number;
  retrievalTopKEffective: number;
  candidateHitCount: number;
  selectedHitCount: number;
  selectedSourceIds: string[];
  selectedTitles: string[];
  weakRetrieval: boolean;
  duplicateHitsRemoved: number;
  failureStage: string | null;
  failureReason: string | null;
}

export interface ProductContentAuditLog {
  id: string;
  taskId: string;
  exportJobId: string | null;
  eventType: string;
  outcome: "success" | "failure";
  summary: string;
  details: Record<string, unknown>;
  createdAt: string;
}

export interface GeneratedContent {
  sellingPointsCopy: string[];
  detailPageCopy: string;
  socialSeedCopy: string;
  riskNotes: string[];
  appliedGuidelines: string[];
}

export interface ProductContentJobDetail {
  id: string;
  status: ProductContentJobStatus;
  currentStage: string;
  errorMessage: string | null;
  product: ProductInput;
  taskDescription: string;
  productBrief: ProductBrief | null;
  sellingStrategy: SellingStrategy | null;
  inputAlerts: string[];
  referenceContext: ReferenceContextItem[];
  retrievalCandidates: ReferenceContextItem[];
  contextSummary: Record<string, unknown>;
  diagnostics?: ProductContentDiagnostics | null;
  processingTrace: string[];
  generatedContent: GeneratedContent | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApiProductContentJobRecord {
  id: string;
  status: ProductContentJobStatus;
  current_stage: string;
  error_message: string | null;
  product: {
    name: string;
    category: string;
    specifications: string[];
    price_range?: string | null;
    core_selling_points: string[];
    target_audience?: string | null;
    use_scenarios: string[];
    promotion_notes?: string | null;
  };
  task_description: string;
  product_brief?: {
    summary: string;
    target_audience?: string | null;
    use_scenarios: string[];
    primary_value_points: string[];
  } | null;
  selling_strategy?: {
    primary_angle: string;
    supporting_angles: string[];
    scenario_focus: string[];
    expression_guardrails: string[];
  } | null;
  input_alerts?: string[];
  reference_context: Array<{
    source_id: string;
    title: string;
    snippet: string;
    reason: string;
  }>;
  retrieval_candidates?: Array<{
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
  }>;
  context_summary?: Record<string, unknown>;
  diagnostics?: {
    generation_provider?: string;
    retrieval_provider?: string;
    retrieval_query?: string;
    retrieval_top_k_requested?: number;
    retrieval_top_k_effective?: number;
    candidate_hit_count?: number;
    selected_hit_count?: number;
    selected_source_ids?: string[];
    selected_titles?: string[];
    weak_retrieval?: boolean;
    duplicate_hits_removed?: number;
    failure_stage?: string | null;
    failure_reason?: string | null;
  } | null;
  processing_trace?: string[];
  generated_content?: {
    selling_points_copy: string[];
    detail_page_copy: string;
    social_seed_copy: string;
    risk_notes: string[];
    applied_guidelines: string[];
  } | null;
  created_at: string;
  updated_at: string;
}

export interface ExportJobSummary {
  id?: string;
  status: "queued" | "exporting" | "completed" | "failed";
  exportType: "markdown" | "structured_text";
  filePath?: string | null;
}

export function splitLines(value: string): string[] {
  return value
    .replace(/[；;、，,]+/g, "\n")
    .split(/\r?\n|\s+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function isJobActive(status: ProductContentJobStatus): boolean {
  return ["queued", "parsing", "understanding", "retrieving", "generating", "exporting"].includes(status);
}

export function getJobStatusLabel(status: ProductContentJobStatus): string {
  const labels: Record<ProductContentJobStatus, string> = {
    queued: "已排队",
    parsing: "解析中",
    understanding: "理解商品中",
    retrieving: "匹配业务资料中",
    generating: "生成初稿中",
    exporting: "导出中",
    completed: "已完成",
    failed: "失败",
  };
  return labels[status];
}
