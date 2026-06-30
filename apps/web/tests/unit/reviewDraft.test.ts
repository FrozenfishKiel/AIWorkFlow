import { describe, expect, it } from "vitest";

import {
  buildReviewDraftFromTask,
  buildReviewUpdatePayload,
  shouldSyncReviewDraft,
} from "../../src/features/task-detail/reviewDraft";

describe("review draft helpers", () => {
  it("builds the draft from the latest task detail snapshot", () => {
    const draft = buildReviewDraftFromTask({
      id: "task-1",
      title: "Example task",
      input_type: "text",
      content: "Original content",
      input_content: "Original content",
      status: "reviewing",
      current_stage: "reviewing",
      error_message: null,
      created_at: "2026-06-30T00:00:00Z",
      updated_at: "2026-06-30T00:10:00Z",
      retrieval_hits: [],
      workflow_result: {
        content_breakdown: "Reviewed draft",
        review_notes: ["Note"],
        pending_review_items: ["Question"],
      },
      review: {
        decision: "in_review",
        reviewer_note: "Keep the structure tight.",
        rejection_reason: null,
        not_adopted_items: ["Removed unsupported metric"],
      },
    });

    expect(draft.draft).toBe("Reviewed draft");
    expect(draft.reviewerNote).toBe("Keep the structure tight.");
    expect(draft.notAdoptedItems).toBe("Removed unsupported metric");
    expect(draft.understandingSummary).toBe("");
  });

  it("does not overwrite dirty local edits during an active review poll refresh", () => {
    expect(shouldSyncReviewDraft({ force: false, isDirty: true, status: "reviewing" })).toBe(false);
  });

  it("allows forced sync after an explicit review action succeeds", () => {
    expect(shouldSyncReviewDraft({ force: true, isDirty: true, status: "reviewing" })).toBe(true);
  });

  it("builds a real review payload from edited understanding and retrieval drafts", () => {
    const payload = buildReviewUpdatePayload(
      {
        understanding_result: {
          summary: "Original summary",
          audience: "brand",
          key_points: ["Original point"],
          risk_points: ["Original risk"],
          uncertain_items: ["Original uncertainty"],
          input_quality: {
            source_kind: "text",
            quality_flags: ["short_input"],
            extracted_length: 32,
          },
        },
        retrieval_hits: [
          {
            title: "Original source",
            source: "doc-1",
            excerpt: "Original excerpt",
            reason: "Original reason",
          },
        ],
        workflow_result: {
          content_breakdown: "Original draft",
          review_notes: ["Review note"],
          pending_review_items: ["Open question"],
        },
      },
      {
        draft: "Edited draft",
        reviewerNote: "Edited before approval.",
        notAdoptedItems: "Dropped claim",
        rejectionReason: "",
        understandingSummary: "Edited summary",
        understandingAudience: "brand\nops",
        understandingKeyPoints: "Point A\nPoint B",
        retrievalHits: [
          {
            title: "Edited source",
            source: "doc-2",
            excerpt: "Edited excerpt",
            reason: "Edited reason",
          },
        ],
      },
    );

    expect(payload.edited_understanding?.summary).toBe("Edited summary");
    expect(payload.edited_understanding?.audience).toEqual(["brand", "ops"]);
    expect(payload.edited_understanding?.risk_points).toEqual(["Original risk"]);
    expect(payload.edited_understanding?.uncertain_items).toEqual(["Original uncertainty"]);
    expect(payload.edited_understanding?.input_quality?.source_kind).toBe("text");
    expect(payload.edited_retrieval_hits?.[0].source_id).toBe("doc-2");
    expect(payload.edited_workflow_result?.draft).toBe("Edited draft");
  });
});
