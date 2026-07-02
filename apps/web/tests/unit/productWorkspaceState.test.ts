import { describe, expect, it } from "vitest";

import { ApiError } from "../../src/services/api";
import { getStoredJobRecoveryAction } from "../../src/pages/productWorkspaceState";

describe("product workspace stored job recovery", () => {
  it("silently clears a stale stored job id when the backend returns 404", () => {
    expect(getStoredJobRecoveryAction(new ApiError("Not Found", 404))).toEqual({
      clearStoredJob: true,
      message: null,
    });
  });

  it("also clears malformed stale ids when the backend rejects them with 422", () => {
    expect(getStoredJobRecoveryAction(new ApiError("validation failed", 422))).toEqual({
      clearStoredJob: true,
      message: null,
    });
  });

  it("keeps surfacing real backend errors instead of swallowing them", () => {
    expect(getStoredJobRecoveryAction(new ApiError("Server error", 500))).toEqual({
      clearStoredJob: false,
      message: "Server error",
    });
  });

  it("keeps plain unknown errors visible", () => {
    expect(getStoredJobRecoveryAction(new Error("Network down"))).toEqual({
      clearStoredJob: false,
      message: "Network down",
    });
  });
});
