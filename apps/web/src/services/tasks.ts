import { apiClient } from "./api";
import type {
  ApiApprovedSnapshot,
  ApiRetrievalHit,
  ApiReviewSnapshot,
  ApiTaskRecord,
  ApiWorkflowResult,
  ExportJob,
  ExportJobCreateInput,
  ReviewRejectInput,
  ReviewRerunInput,
  ReviewUpdateInput,
  TaskCreateFormValues,
  TaskCreateInput,
  TaskDetail,
  TaskListItem,
  UnderstandingResult,
} from "../types/task";
import { getTaskDisplayTitle } from "../types/task";

function toCreatePayload(values: TaskCreateFormValues): TaskCreateInput {
  const knowledgeDomain = values.knowledgeDomain?.trim();
  return {
    input_type: values.inputType,
    content: values.content.trim(),
    ...(knowledgeDomain ? { knowledge_domain: knowledgeDomain } : {}),
  };
}

function toUploadPayload(values: TaskCreateFormValues): FormData {
  if (!values.file) {
    throw new Error("File is required for file tasks.");
  }

  const formData = new FormData();
  formData.append("file", values.file);
  const knowledgeDomain = values.knowledgeDomain?.trim();
  if (knowledgeDomain) {
    formData.append("knowledge_domain", knowledgeDomain);
  }
  return formData;
}

function normalizeUnderstanding(understanding?: UnderstandingResult | null) {
  if (!understanding) {
    return null;
  }

  return {
    summary: understanding.summary,
    audience: understanding.audience.join(", "),
    key_points: understanding.key_points,
    risk_points: understanding.risk_points,
    uncertain_items: understanding.uncertain_items,
    input_quality: understanding.input_quality,
  };
}

function normalizeRetrievalHits(retrievalHits: ApiRetrievalHit[]) {
  return retrievalHits.map((hit) => ({
    title: hit.title,
    source: hit.source_id,
    excerpt: hit.snippet,
    reason: hit.reason,
  }));
}

function normalizeWorkflowResult(workflowResult?: ApiWorkflowResult | null) {
  if (!workflowResult) {
    return null;
  }

  return {
    content_breakdown: workflowResult.draft,
    review_notes: workflowResult.review_notes,
    pending_review_items: workflowResult.open_questions,
    evidence_used: workflowResult.evidence_used.map((item) => ({
      source: item.source_id,
      title: item.title,
    })),
    uncertainties: workflowResult.uncertainties,
    manual_checks: workflowResult.manual_checks,
    context_summary: workflowResult.context_summary,
    processing_trace: workflowResult.processing_trace,
  };
}

function normalizeReview(review?: ApiReviewSnapshot | null) {
  if (!review) {
    return null;
  }

  return {
    decision: review.decision,
    reviewer_note: review.reviewer_note ?? null,
    rejection_reason: review.rejection_reason ?? null,
    rerun_reason: review.rerun_reason ?? null,
    not_adopted_items: review.not_adopted_items ?? [],
  };
}

function normalizeApprovedSnapshot(snapshot?: ApiApprovedSnapshot | null) {
  if (!snapshot) {
    return null;
  }

  return {
    understanding_result: normalizeUnderstanding(snapshot.understanding),
    retrieval_hits: normalizeRetrievalHits(snapshot.retrieval_hits ?? []),
    workflow_result: normalizeWorkflowResult(snapshot.workflow_result),
  };
}

/**
 * Adapts the current backend task payload into the UI shape used by the first
 * task console slice while keeping the raw API contract visible at the edges.
 *
 * Precedence matters here:
 * 1. If an approved snapshot exists, the UI shows only that canonical content.
 * 2. Otherwise the UI prefers reviewer overrides over raw generated output.
 * 3. The raw API record is still spread through so debugging the boundary stays
 *    possible while the backend and frontend shapes continue to evolve.
 */
export function normalizeTaskRecord(task: ApiTaskRecord): TaskDetail {
  const approvedSnapshot = normalizeApprovedSnapshot(task.approved_snapshot);
  const effectiveUnderstanding =
    approvedSnapshot?.understanding_result
      ? null
      : (task.review?.edited_understanding ?? task.understanding);
  const effectiveRetrievalHits =
    approvedSnapshot?.retrieval_hits
      ? []
      : (task.review?.edited_retrieval_hits?.length
        ? task.review.edited_retrieval_hits
        : (task.retrieval_hits ?? []));
  const effectiveWorkflowResult =
    approvedSnapshot?.workflow_result
      ? null
      : (task.review?.edited_workflow_result ?? task.workflow_result);

  return {
    ...task,
    title: getTaskDisplayTitle(task),
    input_content: task.content,
    understanding_result: approvedSnapshot?.understanding_result ?? normalizeUnderstanding(effectiveUnderstanding),
    retrieval_hits: approvedSnapshot?.retrieval_hits ?? normalizeRetrievalHits(effectiveRetrievalHits),
    workflow_result: approvedSnapshot?.workflow_result ?? normalizeWorkflowResult(effectiveWorkflowResult),
    review: normalizeReview(task.review),
  };
}

export async function fetchTaskList(): Promise<TaskListItem[]> {
  const response = await apiClient.get<ApiTaskRecord[]>("/tasks");
  return response.map(normalizeTaskRecord);
}

export async function fetchTaskDetail(taskId: string): Promise<TaskDetail> {
  const response = await apiClient.get<ApiTaskRecord>(`/tasks/${taskId}`);
  return normalizeTaskRecord(response);
}

export async function createTask(values: TaskCreateFormValues): Promise<string> {
  const response =
    values.inputType === "file"
      ? await apiClient.post<ApiTaskRecord>("/tasks/upload", toUploadPayload(values))
      : await apiClient.post<ApiTaskRecord>("/tasks", toCreatePayload(values));
  return response.id;
}

export async function startReview(taskId: string): Promise<TaskDetail> {
  const response = await apiClient.post<ApiTaskRecord>(`/reviews/${taskId}/start`);
  return normalizeTaskRecord(response);
}

export async function saveReview(taskId: string, payload: ReviewUpdateInput): Promise<TaskDetail> {
  const response = await apiClient.put<ApiTaskRecord>(`/reviews/${taskId}`, payload);
  return normalizeTaskRecord(response);
}

export async function approveReview(taskId: string, payload: ReviewUpdateInput): Promise<TaskDetail> {
  const response = await apiClient.post<ApiTaskRecord>(`/reviews/${taskId}/approve`, payload);
  return normalizeTaskRecord(response);
}

export async function rejectReview(taskId: string, payload: ReviewRejectInput): Promise<TaskDetail> {
  const response = await apiClient.post<ApiTaskRecord>(`/reviews/${taskId}/reject`, payload);
  return normalizeTaskRecord(response);
}

export async function rerunReview(taskId: string, payload: ReviewRerunInput): Promise<TaskDetail> {
  const response = await apiClient.post<ApiTaskRecord>(`/reviews/${taskId}/rerun`, payload);
  return normalizeTaskRecord(response);
}

export async function createExportJob(payload: ExportJobCreateInput): Promise<ExportJob> {
  return await apiClient.post<ExportJob>("/exports", payload);
}

export async function fetchExportJob(exportJobId: string): Promise<ExportJob> {
  return await apiClient.get<ExportJob>(`/exports/${exportJobId}`);
}

export async function downloadExportArtifact(exportJobId: string): Promise<Blob> {
  return await apiClient.getBlob(`/exports/${exportJobId}/artifact`);
}
