import { describe, expect, it } from "vitest";

import {
  getTaskStatusMeta,
  isTaskActive,
  summarizeTaskContent,
  type TaskStatus,
} from "../../src/types/task";

describe("task status helpers", () => {
  it("maps review_pending to a readable label and warning tone", () => {
    const meta = getTaskStatusMeta("review_pending");

    expect(meta.label).toBe("Review pending");
    expect(meta.tone).toBe("warning");
  });

  it("treats completed as inactive terminal state", () => {
    expect(isTaskActive("completed")).toBe(false);
  });

  it("treats running statuses as active", () => {
    const activeStatuses: TaskStatus[] = [
      "queued",
      "parsing",
      "understanding",
      "retrieving",
      "generating",
      "reviewing",
      "exporting",
    ];

    expect(activeStatuses.every((status) => isTaskActive(status))).toBe(true);
  });

  it("summarizes file tasks with the uploaded filename", () => {
    expect(
      summarizeTaskContent({
        input_type: "file",
        content: "D:\\uploads\\campaign-brief.pdf",
      }),
    ).toBe("campaign-brief.pdf");
  });

  it("summarizes url tasks with the host name", () => {
    expect(
      summarizeTaskContent({
        input_type: "url",
        content: "https://example.com/articles/brief",
      }),
    ).toBe("example.com");
  });

  it("shows missing content with a stable fallback", () => {
    expect(
      summarizeTaskContent({
        input_type: "text",
        content: "",
      }),
    ).toBe("No content");
  });
});
