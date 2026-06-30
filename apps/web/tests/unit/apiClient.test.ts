import { afterEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("api client auth header", () => {
  it("adds a bearer token header when VITE_API_ACCESS_TOKEN is configured", async () => {
    vi.stubEnv("VITE_API_ACCESS_TOKEN", "front-secret");

    const { apiClient } = await import("../../src/services/api");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });

    await apiClient.get("/tasks");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/tasks",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer front-secret",
        }),
      }),
    );
  });
});
