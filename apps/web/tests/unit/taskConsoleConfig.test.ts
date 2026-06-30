import { describe, expect, it } from "vitest";

import { TASK_CONSOLE_INPUT_TYPES } from "../../src/types/task";

describe("TASK_CONSOLE_INPUT_TYPES", () => {
  it("exposes all task creation inputs wired through the console", () => {
    expect(TASK_CONSOLE_INPUT_TYPES).toEqual(["text", "url", "file"]);
  });
});
