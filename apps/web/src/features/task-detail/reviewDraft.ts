import type { ReviewUpdateInput, TaskDetail, TaskStatus } from "../../types/task";

export interface ReviewRetrievalHitDraft {
  title: string;
  source: string;
  excerpt: string;
  reason: string;
}

export interface ReviewDraftState {
  draft: string;
  reviewerNote: string;
  notAdoptedItems: string;
  rejectionReason: string;
  understandingSummary: string;
  understandingAudience: string;
  understandingKeyPoints: string;
  retrievalHits: ReviewRetrievalHitDraft[];
}

function splitLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

/**
 * Builds the local review form state from the latest persisted task detail.
 *
 * This keeps the editor seeded from the current authoritative backend snapshot
 * while still letting the page protect dirty in-progress reviewer edits.
 */
export function buildReviewDraftFromTask(task: TaskDetail | null): ReviewDraftState {
  return {
    draft: task?.workflow_result?.content_breakdown ?? "",
    reviewerNote: task?.review?.reviewer_note ?? "",
    notAdoptedItems: task?.review?.not_adopted_items?.join("\n") ?? "",
    rejectionReason: task?.review?.rejection_reason ?? "",
    understandingSummary: task?.understanding_result?.summary ?? "",
    understandingAudience: task?.understanding_result?.audience ?? "",
    understandingKeyPoints: (task?.understanding_result?.key_points ?? []).join("\n"),
    retrievalHits: (task?.retrieval_hits ?? []).map((hit) => ({
      title: hit.title,
      source: hit.source,
      excerpt: hit.excerpt,
      reason: hit.reason,
    })),
  };
}

/**
 * Prevents polling refreshes from silently overwriting reviewer edits.
 *
 * Forced sync is only used after explicit review actions succeed, because that
 * means the backend has become the new source of truth again.
 */
export function shouldSyncReviewDraft(input: {
  force: boolean;
  isDirty: boolean;
  status?: TaskStatus | null;
}): boolean {
  if (input.force) {
    return true;
  }

  if (input.isDirty && (input.status === "review_pending" || input.status === "reviewing")) {
    return false;
  }

  return true;
}

/**
 * Converts the local review editor state back into the backend review payload.
 *
 * The current UI always sends the edited sections explicitly so review saves
 * and approvals are deterministic instead of depending on hidden merge logic in
 * the browser.
 */
export function buildReviewUpdatePayload(
  task: Pick<TaskDetail, "workflow_result"> & {
    understanding_result?: TaskDetail["understanding_result"];
    retrieval_hits?: TaskDetail["retrieval_hits"];
  },
  draft: ReviewDraftState,
): ReviewUpdateInput {
  return {
    edited_understanding: {
      summary: draft.understandingSummary.trim(),
      audience: splitLines(draft.understandingAudience.replaceAll(",", "\n")),
      key_points: splitLines(draft.understandingKeyPoints),
      risk_points: task.understanding_result?.risk_points ?? [],
      uncertain_items: task.understanding_result?.uncertain_items ?? [],
      input_quality: task.understanding_result?.input_quality ?? {
        source_kind: "unknown",
        quality_flags: [],
        extracted_length: 0,
      },
    },
    edited_retrieval_hits: draft.retrievalHits.map((hit) => ({
      title: hit.title.trim(),
      source_id: hit.source.trim(),
      snippet: hit.excerpt.trim(),
      reason: hit.reason.trim(),
    })),
    edited_workflow_result: {
      draft: draft.draft.trim(),
      review_notes: task.workflow_result?.review_notes ?? [],
      open_questions: task.workflow_result?.pending_review_items ?? [],
    },
    not_adopted_items: splitLines(draft.notAdoptedItems),
    reviewer_note: draft.reviewerNote.trim() || null,
  };
}
