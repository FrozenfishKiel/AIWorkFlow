import { describe, expect, it } from "vitest";

import { normalizeTaskRecord } from "../../src/services/tasks";

describe("normalizeTaskRecord", () => {
  it("adapts the current backend task payload into UI-friendly fields", () => {
    const normalized = normalizeTaskRecord({
      id: "task-1",
      input_type: "url",
      content: "https://example.com/articles/launch-plan",
      status: "review_pending",
      current_stage: "review_pending",
      error_message: null,
      understanding: {
        summary: "Structured summary",
        audience: ["content-ops", "brand"],
        key_points: ["Keep claims reviewable."],
        risk_points: ["Input is very short"],
        uncertain_items: ["Source content may be incomplete"],
        input_quality: {
          source_kind: "url",
          quality_flags: ["short_input"],
          extracted_length: 42,
          metadata: {
            title: "Launch Plan",
            extractor: "article",
          },
        },
      },
      retrieval_hits: [
        {
          source_id: "kb-brand-guideline",
          title: "Brand tone guideline",
          snippet: "Keep the tone practical.",
          reason: "Provides tone constraints.",
        },
      ],
      workflow_result: {
        draft: "Draft workflow output",
        review_notes: ["Confirm the final business angle."],
        open_questions: ["Does the tone align with the campaign goal?"],
        evidence_used: [
          {
            source_id: "kb-brand-guideline",
            title: "Brand tone guideline",
          },
        ],
        uncertainties: ["Source content may be incomplete"],
        manual_checks: ["Confirm the source article is complete before approval."],
        context_summary: {
          selected_hit_count: 1,
          context_sections: ["task_goal", "input_summary", "retrieval_evidence"],
        },
        processing_trace: [
          "Parsed url input into reviewer-usable plain text.",
          "Assembled a constrained context package before generation.",
        ],
      },
      created_at: "2026-06-30T00:00:00Z",
      updated_at: "2026-06-30T00:05:00Z",
    });

    expect(normalized.id).toBe("task-1");
    expect(normalized.title).toBe("example.com");
    expect(normalized.input_content).toBe("https://example.com/articles/launch-plan");
    expect(normalized.understanding_result?.audience).toBe("content-ops, brand");
    expect(normalized.understanding_result?.risk_points).toEqual(["Input is very short"]);
    expect(normalized.understanding_result?.uncertain_items).toEqual(["Source content may be incomplete"]);
    expect(normalized.understanding_result?.input_quality?.metadata?.extractor).toBe("article");
    expect(normalized.retrieval_hits?.[0].source).toBe("kb-brand-guideline");
    expect(normalized.workflow_result?.content_breakdown).toBe("Draft workflow output");
    expect(normalized.workflow_result?.evidence_used?.[0].source).toBe("kb-brand-guideline");
    expect(normalized.workflow_result?.manual_checks).toEqual(["Confirm the source article is complete before approval."]);
    expect(normalized.workflow_result?.pending_review_items).toEqual([
      "Does the tone align with the campaign goal?",
    ]);
  });

  it("prefers reviewer-edited fields when a review snapshot exists", () => {
    const normalized = normalizeTaskRecord({
      id: "task-2",
      input_type: "text",
      content: "Original content",
      status: "approved",
      current_stage: "approved",
      error_message: null,
      understanding: {
        summary: "Generated summary",
        audience: ["brand"],
        key_points: ["Generated point"],
      },
      retrieval_hits: [
        {
          source_id: "kb-generated",
          title: "Generated source",
          snippet: "Generated snippet",
          reason: "Generated reason",
        },
      ],
      workflow_result: {
        draft: "Generated draft",
        review_notes: ["Generated note"],
        open_questions: ["Generated question"],
      },
      review: {
        decision: "approved",
        reviewer_note: "Edited before approval.",
        rejection_reason: null,
        not_adopted_items: ["Removed unsupported claim"],
        edited_understanding: {
          summary: "Edited summary",
          audience: ["brand", "ops"],
          key_points: ["Edited point"],
          risk_points: ["Edited risk"],
          uncertain_items: ["Edited uncertainty"],
          input_quality: {
            source_kind: "text",
            quality_flags: [],
            extracted_length: 120,
          },
        },
        edited_retrieval_hits: [
          {
            source_id: "kb-edited",
            title: "Edited source",
            snippet: "Edited snippet",
            reason: "Edited reason",
          },
        ],
        edited_workflow_result: {
          draft: "Edited draft",
          review_notes: ["Edited note"],
          open_questions: ["Edited question"],
        },
      },
      approved_snapshot: {
        understanding: {
          summary: "Approved summary",
          audience: ["brand", "ops"],
          key_points: ["Approved point"],
          risk_points: ["Approved risk"],
          uncertain_items: ["Approved uncertainty"],
          input_quality: {
            source_kind: "text",
            quality_flags: [],
            extracted_length: 120,
          },
        },
        retrieval_hits: [
          {
            source_id: "kb-approved",
            title: "Approved source",
            snippet: "Approved snippet",
            reason: "Approved reason",
          },
        ],
        workflow_result: {
          draft: "Approved draft",
          review_notes: ["Approved note"],
          open_questions: ["Approved question"],
          evidence_used: [
            {
              source_id: "kb-approved",
              title: "Approved source",
            },
          ],
          uncertainties: ["Approved uncertainty"],
          manual_checks: ["Approved manual check"],
          context_summary: {
            selected_hit_count: 1,
            context_sections: ["task_goal", "retrieval_evidence"],
          },
          processing_trace: ["Approved trace entry"],
        },
      },
      created_at: "2026-06-30T00:00:00Z",
      updated_at: "2026-06-30T00:10:00Z",
    });

    expect(normalized.review?.decision).toBe("approved");
    expect(normalized.review?.reviewer_note).toBe("Edited before approval.");
    expect(normalized.review?.not_adopted_items).toEqual(["Removed unsupported claim"]);
    expect(normalized.understanding_result?.summary).toBe("Approved summary");
    expect(normalized.understanding_result?.audience).toBe("brand, ops");
    expect(normalized.understanding_result?.risk_points).toEqual(["Approved risk"]);
    expect(normalized.retrieval_hits?.[0].source).toBe("kb-approved");
    expect(normalized.workflow_result?.content_breakdown).toBe("Approved draft");
    expect(normalized.workflow_result?.processing_trace).toEqual(["Approved trace entry"]);
  });
});
