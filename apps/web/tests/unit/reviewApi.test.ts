import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveReview,
  createExportJob,
  createTask,
  downloadExportArtifact,
  fetchExportJob,
  rejectReview,
  rerunReview,
  saveReview,
  startReview,
} from "../../src/services/tasks";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

afterEach(() => {
  fetchMock.mockReset();
});

describe("review task service calls", () => {
  it("posts start review to the dedicated review endpoint", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "task-1" }),
    });

    await startReview("task-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/reviews/task-1/start",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("sends save, approve, and reject payloads to the matching endpoints", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "task-1" }),
    });

    await saveReview("task-1", {
      edited_understanding: {
        summary: "Edited summary",
        audience: ["brand"],
        key_points: ["Point"],
      },
      edited_retrieval_hits: [],
      edited_workflow_result: {
        draft: "Edited draft",
        review_notes: [],
        open_questions: [],
      },
      not_adopted_items: ["Dropped claim"],
      reviewer_note: "Saved for later approval.",
    });
    await approveReview("task-1", {
      edited_understanding: null,
      edited_retrieval_hits: [],
      edited_workflow_result: null,
      not_adopted_items: [],
      reviewer_note: "Approved.",
    });
    await rejectReview("task-1", {
      rejection_reason: "Unsupported claim.",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/reviews/task-1",
      expect.objectContaining({
        method: "PUT",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/reviews/task-1/approve",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/reviews/task-1/reject",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("posts export requests to the export endpoint", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "export-1" }),
    });

    await createExportJob({
      task_id: "task-1",
      export_type: "markdown",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/exports",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("posts multipart file uploads to the dedicated upload endpoint", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "task-file-1" }),
    });

    await createTask({
      inputType: "file",
      content: "",
      knowledgeDomain: "brand",
      file: new File(["brief"], "launch-brief.md", { type: "text/markdown" }),
    });

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/tasks/upload", expect.any(Object));
    const [, init] = fetchMock.mock.calls[0] as [string, { body: FormData; method: string }];
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.body.get("knowledge_domain")).toBe("brand");
  });

  it("includes knowledge domain in json task creation payloads", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "task-1" }),
    });

    await createTask({
      inputType: "text",
      content: "Need launch messaging.",
      knowledgeDomain: "compliance",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/tasks",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          input_type: "text",
          content: "Need launch messaging.",
          knowledge_domain: "compliance",
        }),
      }),
    );
  });

  it("fetches export status and downloads export artifacts through dedicated endpoints", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: "export-1", status: "completed" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        blob: async () => new Blob(["export body"], { type: "text/markdown" }),
      });

    await fetchExportJob("export-1");
    await downloadExportArtifact("export-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/exports/export-1",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/exports/export-1/artifact",
      expect.objectContaining({
        headers: expect.any(Object),
      }),
    );
  });

  it("posts rerun requests to the review rerun endpoint", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "task-1" }),
    });

    await rerunReview("task-1", {
      rerun_reason: "Regenerate with a safer angle.",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/reviews/task-1/rerun",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });
});
