import { afterEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllEnvs();
  vi.resetModules();
});

function createStorageMock() {
  const store = new Map<string, string>();
  return {
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
  };
}

describe("api client auth header", () => {
  it("adds a bearer token header when VITE_API_ACCESS_TOKEN is configured", async () => {
    vi.stubEnv("VITE_API_ACCESS_TOKEN", "front-secret");

    const { apiClient } = await import("../../src/services/api");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });

    await apiClient.get("/product-content/jobs/example-id");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/product-content/jobs/example-id",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer front-secret",
        }),
      }),
    );
  });

  it("falls back to a stored login token when no build-time token is configured", async () => {
    vi.stubGlobal("localStorage", createStorageMock());

    const { apiClient, setStoredAccessToken } = await import("../../src/services/api");

    setStoredAccessToken("session-secret");
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });

    await apiClient.get("/product-content/jobs/example-id");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/product-content/jobs/example-id",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer session-secret",
        }),
      }),
    );
  });
});

describe("auth api", () => {
  it("posts credentials to the login endpoint and persists the returned session", async () => {
    vi.stubGlobal("localStorage", createStorageMock());

    const { loginOperator, readStoredAuthSession } = await import("../../src/services/auth");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: "issued-token",
        token_type: "bearer",
        username: "operator",
        auth_mode: "password_login",
        expires_at: "2026-07-02T10:00:00Z",
      }),
    });

    const session = await loginOperator({
      username: "operator",
      password: "open-sesame",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/login",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(session.access_token).toBe("issued-token");
    expect(readStoredAuthSession()?.username).toBe("operator");
  });
});

describe("export api", () => {
  it("requests the export job detail from the dedicated endpoint", async () => {
    const { fetchExportJob } = await import("../../src/services/exports");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: "export-1",
        task_id: "task-1",
        export_type: "markdown",
        status: "completed",
        file_path: ".runtime/exports/export-1.md",
        error_message: null,
        created_at: "2026-07-01T00:05:00Z",
        updated_at: "2026-07-01T00:05:30Z",
      }),
    });

    const exportJob = await fetchExportJob("export-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/exports/export-1",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    expect(exportJob.id).toBe("export-1");
    expect(exportJob.export_type).toBe("markdown");
    expect(exportJob.status).toBe("completed");
  });
});

describe("api error normalization", () => {
  it("does not surface object-shaped validation errors as [object Object]", async () => {
    const { apiClient, ApiError } = await import("../../src/services/api");

    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      headers: {
        get(name: string) {
          return name.toLowerCase() === "content-type" ? "application/json" : null;
        },
      },
      json: async () => ({
        detail: [
          {
            loc: ["path", "task_id"],
            msg: "Input should be a valid UUID",
          },
        ],
      }),
    });

    await expect(apiClient.get("/product-content/jobs/not-a-uuid")).rejects.toMatchObject<ApiError>({
      status: 422,
      message: expect.not.stringContaining("[object Object]"),
    });
  });
});
