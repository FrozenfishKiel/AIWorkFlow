import { useEffect, useMemo, useState } from "react";

import { TaskCreateForm } from "../features/task-create/TaskCreateForm";
import {
  buildReviewDraftFromTask,
  buildReviewUpdatePayload,
  shouldSyncReviewDraft,
} from "../features/task-detail/reviewDraft";
import { TaskDetailView } from "../features/task-detail/TaskDetailView";
import {
  approveReview,
  createExportJob,
  createTask,
  downloadExportArtifact,
  fetchTaskDetail,
  fetchExportJob,
  fetchTaskList,
  rejectReview,
  rerunReview,
  saveReview,
  startReview,
} from "../services/tasks";
import {
  getTaskStatusMeta,
  isTaskActive,
  summarizeTaskContent,
  type ExportJob,
  type TaskDetail,
  type TaskListItem,
} from "../types/task";

// Phase 1 deliberately uses simple polling instead of websocket state sync so
// the first end-to-end slice stays easier to run, debug, and document.
const POLLING_INTERVAL_MS = 4000;

export function TaskConsolePage() {
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<TaskDetail | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [reviewActionLoading, setReviewActionLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [error, setError] = useState("");
  const [reviewDraft, setReviewDraft] = useState(buildReviewDraftFromTask(null));
  const [reviewDraftDirty, setReviewDraftDirty] = useState(false);
  const [latestExportJob, setLatestExportJob] = useState<ExportJob | null>(null);

  const selectedListTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, tasks],
  );

  async function loadTasks() {
    try {
      setError("");
      const items = await fetchTaskList();
      setTasks(items);

      if (!selectedTaskId && items.length > 0) {
        setSelectedTaskId(items[0].id);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load tasks.");
    } finally {
      setListLoading(false);
    }
  }

  async function loadTaskDetail(taskId: string, options?: { forceReviewDraftSync?: boolean }) {
    try {
      setDetailLoading(true);
      const task = await fetchTaskDetail(taskId);
      setSelectedTask(task);
      if (
        shouldSyncReviewDraft({
          force: options?.forceReviewDraftSync ?? false,
          isDirty: reviewDraftDirty,
          status: task.status,
        })
      ) {
        setReviewDraft(buildReviewDraftFromTask(task));
        setReviewDraftDirty(false);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load task detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    void loadTasks();
  }, []);

  useEffect(() => {
    if (!selectedTaskId) {
      setSelectedTask(null);
      return;
    }

    void loadTaskDetail(selectedTaskId, { forceReviewDraftSync: true });

    // Only active pipeline states keep polling; terminal states stop to avoid
    // unnecessary traffic and to make later review/export transitions explicit.
    if (!selectedListTask || !isTaskActive(selectedListTask.status)) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadTasks();
      void loadTaskDetail(selectedTaskId);
    }, POLLING_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [selectedListTask, selectedTaskId]);

  useEffect(() => {
    if (!latestExportJob || latestExportJob.status === "completed" || latestExportJob.status === "failed") {
      return;
    }

    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const refreshed = await fetchExportJob(latestExportJob.id);
          setLatestExportJob(refreshed);
          if (refreshed.status === "completed") {
            await loadTasks();
            if (selectedTaskId) {
              await loadTaskDetail(selectedTaskId, { forceReviewDraftSync: true });
            }
          }
        } catch (loadError) {
          setError(loadError instanceof Error ? loadError.message : "Failed to refresh export job.");
        }
      })();
    }, POLLING_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [latestExportJob, selectedTaskId]);

  async function handleCreate(values: Parameters<typeof createTask>[0]) {
    setSubmitLoading(true);
    try {
      const taskId = await createTask(values);
      setSelectedTaskId(taskId);
      await loadTasks();
      await loadTaskDetail(taskId, { forceReviewDraftSync: true });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to create task.");
    } finally {
      setSubmitLoading(false);
    }
  }

  function handleReviewDraftChange(
    field:
      | "draft"
      | "reviewerNote"
      | "notAdoptedItems"
      | "rejectionReason"
      | "understandingSummary"
      | "understandingAudience"
      | "understandingKeyPoints",
    value: string,
  ) {
    setReviewDraft((current) => ({
      ...current,
      [field]: value,
    }));
    setReviewDraftDirty(true);
  }

  function handleReviewRetrievalHitChange(
    index: number,
    field: "title" | "source" | "excerpt" | "reason",
    value: string,
  ) {
    setReviewDraft((current) => ({
      ...current,
      retrievalHits: current.retrievalHits.map((hit, hitIndex) =>
        hitIndex === index ? { ...hit, [field]: value } : hit,
      ),
    }));
    setReviewDraftDirty(true);
  }

  function handleAddReviewRetrievalHit() {
    setReviewDraft((current) => ({
      ...current,
      retrievalHits: [
        ...current.retrievalHits,
        { title: "", source: "", excerpt: "", reason: "" },
      ],
    }));
    setReviewDraftDirty(true);
  }

  function handleRemoveReviewRetrievalHit(index: number) {
    setReviewDraft((current) => ({
      ...current,
      retrievalHits: current.retrievalHits.filter((_, hitIndex) => hitIndex !== index),
    }));
    setReviewDraftDirty(true);
  }

  function toReviewPayload(task: TaskDetail) {
    return buildReviewUpdatePayload(task, reviewDraft);
  }

  async function handleReviewStart() {
    if (!selectedTaskId) {
      return;
    }

    setReviewActionLoading(true);
    try {
      const task = await startReview(selectedTaskId);
      setSelectedTask(task);
      setReviewDraft(buildReviewDraftFromTask(task));
      setReviewDraftDirty(false);
      await loadTasks();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to start review.");
    } finally {
      setReviewActionLoading(false);
    }
  }

  async function handleReviewSave() {
    if (!selectedTaskId || !selectedTask) {
      return;
    }

    setReviewActionLoading(true);
    try {
      const task = await saveReview(selectedTaskId, toReviewPayload(selectedTask));
      setSelectedTask(task);
      setReviewDraft(buildReviewDraftFromTask(task));
      setReviewDraftDirty(false);
      await loadTasks();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to save review.");
    } finally {
      setReviewActionLoading(false);
    }
  }

  async function handleReviewApprove() {
    if (!selectedTaskId || !selectedTask) {
      return;
    }

    setReviewActionLoading(true);
    try {
      const task = await approveReview(selectedTaskId, toReviewPayload(selectedTask));
      setSelectedTask(task);
      setReviewDraft(buildReviewDraftFromTask(task));
      setReviewDraftDirty(false);
      await loadTasks();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to approve review.");
    } finally {
      setReviewActionLoading(false);
    }
  }

  async function handleReviewReject() {
    if (!selectedTaskId || !reviewDraft.rejectionReason.trim()) {
      return;
    }

    setReviewActionLoading(true);
    try {
      const task = await rejectReview(selectedTaskId, {
        rejection_reason: reviewDraft.rejectionReason.trim(),
      });
      setSelectedTask(task);
      setReviewDraft(buildReviewDraftFromTask(task));
      setReviewDraftDirty(false);
      await loadTasks();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to reject review.");
    } finally {
      setReviewActionLoading(false);
    }
  }

  async function handleExportMarkdown() {
    if (!selectedTaskId) {
      return;
    }

    setExportLoading(true);
    try {
      const job = await createExportJob({
        task_id: selectedTaskId,
        export_type: "markdown",
      });
      setLatestExportJob(job);
      await loadTasks();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to create export job.");
    } finally {
      setExportLoading(false);
    }
  }

  async function handleDownloadExport() {
    if (!latestExportJob) {
      return;
    }

    try {
      const blob = await downloadExportArtifact(latestExportJob.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      const extension = latestExportJob.export_type === "markdown" ? "md" : "txt";
      link.href = url;
      link.download = `${latestExportJob.id}.${extension}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to download export artifact.");
    }
  }

  async function handleReviewRerun() {
    if (!selectedTaskId || !reviewDraft.rejectionReason.trim()) {
      return;
    }

    setReviewActionLoading(true);
    try {
      const task = await rerunReview(selectedTaskId, {
        rerun_reason: reviewDraft.rejectionReason.trim(),
      });
      setSelectedTask(task);
      setReviewDraft(buildReviewDraftFromTask(task));
      setReviewDraftDirty(false);
      await loadTasks();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to rerun task.");
    } finally {
      setReviewActionLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Task console</p>
        <h1>AI content production ops workflow</h1>
        <p className="hero__copy">
          Create a task, watch it move through the async pipeline, and inspect understanding, retrieval, and workflow outputs.
        </p>
      </header>

      {error ? <div className="alert">{error}</div> : null}

      <div className="layout">
        <div className="column">
          <TaskCreateForm onSubmit={handleCreate} isSubmitting={submitLoading} />

          <section className="panel">
            <div className="panel__header">
              <h2>Task list</h2>
              <p>{listLoading ? "Loading tasks..." : `${tasks.length} tasks`}</p>
            </div>

            <div className="stack">
              {tasks.map((task) => {
                const status = getTaskStatusMeta(task.status);
                const isSelected = task.id === selectedTaskId;

                return (
                  <button
                    key={task.id}
                    type="button"
                    className={`task-card ${isSelected ? "task-card--selected" : ""}`}
                    onClick={() => setSelectedTaskId(task.id)}
                  >
                    <div className="task-card__row">
                      <strong>{task.title}</strong>
                      <span className={`badge badge--${status.tone}`}>{status.label}</span>
                    </div>
                    <p className="muted">{summarizeTaskContent({ input_type: task.input_type, content: task.content })}</p>
                    <p className="muted">{task.current_stage ? `${task.current_stage} | ` : ""}{task.updated_at}</p>
                  </button>
                );
              })}

              {!listLoading && tasks.length === 0 ? <p className="muted">No tasks yet.</p> : null}
            </div>
          </section>
        </div>

        <div className="column column--wide">
          <TaskDetailView
            task={selectedTask}
            isLoading={detailLoading && !selectedTask}
            reviewDraft={reviewDraft}
            actionLoading={reviewActionLoading}
            exportLoading={exportLoading}
            exportJob={
              latestExportJob && latestExportJob.task_id === selectedTaskId
                ? {
                    id: latestExportJob.id,
                    status: latestExportJob.status,
                    exportType: latestExportJob.export_type,
                    filePath: latestExportJob.file_path,
                  }
                : null
            }
            onReviewStart={handleReviewStart}
            onReviewSave={handleReviewSave}
            onReviewApprove={handleReviewApprove}
            onReviewReject={handleReviewReject}
            onReviewRerun={handleReviewRerun}
            onExportMarkdown={handleExportMarkdown}
            onDownloadExport={handleDownloadExport}
            onReviewDraftChange={handleReviewDraftChange}
            onReviewRetrievalHitChange={handleReviewRetrievalHitChange}
            onAddReviewRetrievalHit={handleAddReviewRetrievalHit}
            onRemoveReviewRetrievalHit={handleRemoveReviewRetrievalHit}
          />

          <section className="panel">
            <div className="panel__header">
              <h2>Status snapshot</h2>
              <p>Current selection and poll state.</p>
            </div>

            {selectedListTask ? (
              <div className="snapshot">
                <div>
                  <span className="muted">Selected task</span>
                  <strong>{selectedListTask.title}</strong>
                </div>
                <div>
                  <span className="muted">Status</span>
                  <strong>{getTaskStatusMeta(selectedListTask.status).label}</strong>
                </div>
                <div>
                  <span className="muted">Polling</span>
                  <strong>{isTaskActive(selectedListTask.status) ? "Enabled" : "Stopped"}</strong>
                </div>
              </div>
            ) : (
              <p className="muted">Select a task to inspect it.</p>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
