import type { TaskDetail } from "../../types/task";
import type { ReviewDraftState } from "./reviewDraft";
import { getTaskStatusMeta, summarizeTaskContent } from "../../types/task";

export interface TaskDetailViewProps {
  task: TaskDetail | null;
  isLoading?: boolean;
  reviewDraft?: ReviewDraftState;
  actionLoading?: boolean;
  exportLoading?: boolean;
  exportJob?: {
    id?: string;
    status: string;
    exportType: string;
    filePath?: string | null;
  } | null;
  onReviewStart?: () => void;
  onReviewSave?: () => void;
  onReviewApprove?: () => void;
  onReviewReject?: () => void;
  onReviewRerun?: () => void;
  onExportMarkdown?: () => void;
  onDownloadExport?: () => void;
  onReviewDraftChange?: (
    field:
      | "draft"
      | "reviewerNote"
      | "notAdoptedItems"
      | "rejectionReason"
      | "understandingSummary"
      | "understandingAudience"
      | "understandingKeyPoints",
    value: string,
  ) => void;
  onReviewRetrievalHitChange?: (
    index: number,
    field: "title" | "source" | "excerpt" | "reason",
    value: string,
  ) => void;
  onAddReviewRetrievalHit?: () => void;
  onRemoveReviewRetrievalHit?: (index: number) => void;
}

function formatList(items?: string[] | null, emptyLabel = "None") {
  if (!items?.length) {
    return emptyLabel;
  }

  return items.join(", ");
}

function formatHits(task: TaskDetail) {
  if (!task.retrieval_hits?.length) {
    return <p className="muted">No retrieval hits yet.</p>;
  }

  return (
    <div className="stack">
      {task.retrieval_hits.map((hit, index) => (
        <article className="hit-card" key={`${hit.title}-${index}`}>
          <strong>{hit.title}</strong>
          <p className="muted">{hit.source}</p>
          <p>{hit.excerpt}</p>
          <p className="muted">Reason: {hit.reason}</p>
        </article>
      ))}
    </div>
  );
}

/**
 * Detail view for task inspection. It keeps all structured pipeline output in
 * one place so reviewers can see what the backend produced without hunting.
 */
export function TaskDetailView({
  task,
  isLoading = false,
  reviewDraft,
  actionLoading = false,
  exportLoading = false,
  exportJob = null,
  onReviewStart,
  onReviewSave,
  onReviewApprove,
  onReviewReject,
  onReviewRerun,
  onExportMarkdown,
  onDownloadExport,
  onReviewDraftChange,
  onReviewRetrievalHitChange,
  onAddReviewRetrievalHit,
  onRemoveReviewRetrievalHit,
}: TaskDetailViewProps) {
  if (isLoading) {
    return (
      <section className="panel">
        <div className="panel__header">
          <h2>Task detail</h2>
          <p>Loading latest task data...</p>
        </div>
      </section>
    );
  }

  if (!task) {
    return (
      <section className="panel">
        <div className="panel__header">
          <h2>Task detail</h2>
          <p>Select a task to inspect its pipeline output.</p>
        </div>
      </section>
    );
  }

  const status = getTaskStatusMeta(task.status);
  const canStartReview = task.status === "review_pending";
  const canActInReview = task.status === "review_pending" || task.status === "reviewing";
  const canRerun = task.status === "rejected";
  const canExport = task.status === "approved";
  const reviewDecision = task.review?.decision ?? null;

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>{task.title}</h2>
        <p>
          <span className={`badge badge--${status.tone}`}>{status.label}</span>
          <span className="muted"> {status.description}</span>
        </p>
      </div>

      <div className="detail-grid">
        <div>
          <h3>Task input</h3>
          <p className="muted">{task.input_type.toUpperCase()}</p>
          <p>{summarizeTaskContent({ input_type: task.input_type, content: task.input_content })}</p>
        </div>

        <div>
          <h3>Understanding</h3>
          {task.understanding_result ? (
            <div className="stack">
              <p>{task.understanding_result.summary ?? "No summary provided."}</p>
              <p className="muted">Audience: {task.understanding_result.audience ?? "Unknown"}</p>
              <p className="muted">Key points: {formatList(task.understanding_result.key_points)}</p>
              <p className="muted">
                Risk points: {formatList(task.understanding_result.risk_points, "Not produced in this slice.")}
              </p>
              <p className="muted">
                Uncertain items: {formatList(task.understanding_result.uncertain_items, "Not produced in this slice.")}
              </p>
              <p className="muted">
                Input quality: {task.understanding_result.input_quality
                  ? `${task.understanding_result.input_quality.source_kind}, ${task.understanding_result.input_quality.extracted_length} chars`
                  : "Not produced in this slice."}
              </p>
              <p className="muted">
                Input metadata: {task.understanding_result.input_quality?.metadata
                  ? [
                      task.understanding_result.input_quality.metadata.title
                        ? `title: ${task.understanding_result.input_quality.metadata.title}`
                        : null,
                      task.understanding_result.input_quality.metadata.extractor
                        ? `extractor: ${task.understanding_result.input_quality.metadata.extractor}`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(", ") || "Available"
                  : "None"}
              </p>
              <p className="muted">
                Quality flags: {formatList(task.understanding_result.input_quality?.quality_flags, "None")}
              </p>
            </div>
          ) : (
            <p className="muted">No understanding result yet.</p>
          )}
        </div>

        <div>
          <h3>Retrieval hits</h3>
          {formatHits(task)}
        </div>

        <div>
          <h3>Workflow result</h3>
          <p className="muted">
            {task.review
              ? "Current values reflect the latest reviewer-approved or reviewer-edited snapshot."
              : "Current values come from the first deterministic pipeline slice, not the final review/export flow."}
          </p>
          {task.workflow_result ? (
            <div className="stack">
              <p>{task.workflow_result.content_breakdown ?? "No workflow summary."}</p>
              <p className="muted">Review notes: {formatList(task.workflow_result.review_notes)}</p>
              <p className="muted">
                Pending review items: {formatList(task.workflow_result.pending_review_items)}
              </p>
              <p className="muted">
                Uncertainties: {formatList(task.workflow_result.uncertainties, "None")}
              </p>
              <p className="muted">
                Manual checks: {formatList(task.workflow_result.manual_checks, "None")}
              </p>
              <p className="muted">
                Context sections: {formatList(task.workflow_result.context_summary?.context_sections, "Not produced")}
              </p>
              <p className="muted">
                Selected evidence count: {task.workflow_result.context_summary?.selected_hit_count ?? 0}
              </p>
              <div className="stack">
                <strong>Evidence used</strong>
                {task.workflow_result.evidence_used?.length ? (
                  task.workflow_result.evidence_used.map((item, index) => (
                    <p className="muted" key={`${item.source}-${index}`}>
                      {item.title} ({item.source})
                    </p>
                  ))
                ) : (
                  <p className="muted">No explicit evidence summary yet.</p>
                )}
              </div>
              <div className="stack">
                <strong>Processing trace</strong>
                {task.workflow_result.processing_trace?.length ? (
                  task.workflow_result.processing_trace.map((item, index) => (
                    <p className="muted" key={`${item}-${index}`}>
                      {item}
                    </p>
                  ))
                ) : (
                  <p className="muted">No processing trace yet.</p>
                )}
              </div>
            </div>
          ) : (
            <p className="muted">No workflow result yet.</p>
          )}
        </div>

        <div>
          <h3>Review gate</h3>
          <p className="muted">
            Decision: {reviewDecision ?? "Not started"}
          </p>
          {task.review?.reviewer_note ? <p className="muted">Reviewer note: {task.review.reviewer_note}</p> : null}
          {task.review?.rejection_reason ? (
            <p className="muted">Rejection reason: {task.review.rejection_reason}</p>
          ) : null}
          {task.review?.not_adopted_items?.length ? (
            <p className="muted">Not adopted: {formatList(task.review.not_adopted_items)}</p>
          ) : null}
          <p className="muted">Review actions are available directly in the task console panel.</p>
        </div>

        <div>
          <h3>Export</h3>
          {exportJob ? (
            <div className="stack">
              <p className="muted">Latest export: {exportJob.exportType}</p>
              <p className="muted">Status: {exportJob.status}</p>
              {exportJob.filePath ? <p className="muted">Artifact: {exportJob.filePath}</p> : null}
              {exportJob.status === "completed" ? (
                <button type="button" className="button-secondary" onClick={onDownloadExport}>
                  Download artifact
                </button>
              ) : null}
            </div>
          ) : (
            <p className="muted">No export job yet.</p>
          )}

          {canExport ? (
            <button type="button" className="button-secondary" onClick={onExportMarkdown} disabled={exportLoading}>
              Export markdown
            </button>
          ) : (
            <p className="muted">Export unlocks after review approval.</p>
          )}
        </div>
      </div>

      {canStartReview || canActInReview || canRerun ? (
        <section className="review-panel">
          <div className="panel__header">
            <h3>Review actions</h3>
            <p>Save edits before approval so export uses the reviewed version.</p>
          </div>

          <div className="stack">
            {canStartReview ? (
              <button type="button" onClick={onReviewStart} disabled={actionLoading}>
                Start review
              </button>
            ) : null}

            {canActInReview ? (
              <>
                <label className="field">
                  <span>Understanding summary</span>
                  <textarea
                    rows={3}
                    value={reviewDraft?.understandingSummary ?? ""}
                    onChange={(event) => onReviewDraftChange?.("understandingSummary", event.target.value)}
                    placeholder="Edit the structured understanding summary."
                  />
                </label>

                <label className="field">
                  <span>Understanding audience</span>
                  <textarea
                    rows={3}
                    value={reviewDraft?.understandingAudience ?? ""}
                    onChange={(event) => onReviewDraftChange?.("understandingAudience", event.target.value)}
                    placeholder="One audience per line."
                  />
                </label>

                <label className="field">
                  <span>Understanding key points</span>
                  <textarea
                    rows={4}
                    value={reviewDraft?.understandingKeyPoints ?? ""}
                    onChange={(event) => onReviewDraftChange?.("understandingKeyPoints", event.target.value)}
                    placeholder="One key point per line."
                  />
                </label>

                <div className="stack">
                  <div className="task-card__row">
                    <strong>Retrieval hits</strong>
                    <button type="button" className="button-secondary" onClick={onAddReviewRetrievalHit} disabled={actionLoading}>
                      Add hit
                    </button>
                  </div>

                  {reviewDraft?.retrievalHits.map((hit, index) => (
                    <article key={`${hit.source}-${index}`} className="hit-card stack">
                      <label className="field">
                        <span>Title</span>
                        <input
                          value={hit.title}
                          onChange={(event) => onReviewRetrievalHitChange?.(index, "title", event.target.value)}
                        />
                      </label>
                      <label className="field">
                        <span>Source</span>
                        <input
                          value={hit.source}
                          onChange={(event) => onReviewRetrievalHitChange?.(index, "source", event.target.value)}
                        />
                      </label>
                      <label className="field">
                        <span>Excerpt</span>
                        <textarea
                          rows={3}
                          value={hit.excerpt}
                          onChange={(event) => onReviewRetrievalHitChange?.(index, "excerpt", event.target.value)}
                        />
                      </label>
                      <label className="field">
                        <span>Reason</span>
                        <textarea
                          rows={2}
                          value={hit.reason}
                          onChange={(event) => onReviewRetrievalHitChange?.(index, "reason", event.target.value)}
                        />
                      </label>
                      <button
                        type="button"
                        className="button-danger"
                        onClick={() => onRemoveReviewRetrievalHit?.(index)}
                        disabled={actionLoading}
                      >
                        Remove hit
                      </button>
                    </article>
                  ))}
                </div>

                <label className="field">
                  <span>Reviewed workflow draft</span>
                  <textarea
                    rows={8}
                    value={reviewDraft?.draft ?? ""}
                    onChange={(event) => onReviewDraftChange?.("draft", event.target.value)}
                    placeholder="Edit the workflow draft that should be carried into export."
                  />
                </label>

                <label className="field">
                  <span>Reviewer note</span>
                  <textarea
                    rows={3}
                    value={reviewDraft?.reviewerNote ?? ""}
                    onChange={(event) => onReviewDraftChange?.("reviewerNote", event.target.value)}
                    placeholder="Record why you changed or accepted the current output."
                  />
                </label>

                <label className="field">
                  <span>Not adopted items</span>
                  <textarea
                    rows={3}
                    value={reviewDraft?.notAdoptedItems ?? ""}
                    onChange={(event) => onReviewDraftChange?.("notAdoptedItems", event.target.value)}
                    placeholder="One item per line for claims or parts you rejected."
                  />
                </label>

                <div className="review-actions">
                  <button type="button" onClick={onReviewSave} disabled={actionLoading}>
                    Save review
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={onReviewApprove}
                    disabled={actionLoading}
                  >
                    Approve
                  </button>
                </div>

                <label className="field">
                  <span>Rejection reason</span>
                  <textarea
                    rows={3}
                    value={reviewDraft?.rejectionReason ?? ""}
                    onChange={(event) => onReviewDraftChange?.("rejectionReason", event.target.value)}
                    placeholder="Only required if the current output must be rejected."
                  />
                </label>

                <button
                  type="button"
                  className="button-danger"
                  onClick={onReviewReject}
                  disabled={actionLoading || !(reviewDraft?.rejectionReason ?? "").trim()}
                >
                  Reject
                </button>
              </>
            ) : null}

            {canRerun ? (
              <>
                <label className="field">
                  <span>Rerun reason</span>
                  <textarea
                    rows={3}
                    value={reviewDraft?.rejectionReason ?? ""}
                    onChange={(event) => onReviewDraftChange?.("rejectionReason", event.target.value)}
                    placeholder="Explain what should change when the task is regenerated."
                  />
                </label>
                <button
                  type="button"
                  className="button-secondary"
                  onClick={onReviewRerun}
                  disabled={actionLoading || !(reviewDraft?.rejectionReason ?? "").trim()}
                >
                  Rerun task
                </button>
              </>
            ) : null}
          </div>
        </section>
      ) : null}
    </section>
  );
}
