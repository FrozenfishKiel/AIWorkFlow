import { afterEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

afterEach(() => {
  fetchMock.mockReset();
  vi.resetModules();
});

describe("runtime config api", () => {
  it("loads current local runtime setup state from the backend", async () => {
    const { fetchRuntimeConfig } = await import("../../src/services/runtimeConfig");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        env_file_path: "D:/project/apps/api/.env.local",
        setup_required: true,
        deepseek_configured: false,
        deepseek_api_base_url: "https://api.deepseek.com",
        deepseek_model: "deepseek-v4-flash",
        task_generation_provider: "auto",
        retrieval_profile_provider: "auto",
        missing_required_settings: ["DEEPSEEK_API_KEY"],
      }),
    });

    const config = await fetchRuntimeConfig();

    expect(config.setup_required).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/runtime-config",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("persists local deepseek setup without exposing the secret in the response", async () => {
    const { updateRuntimeConfig } = await import("../../src/services/runtimeConfig");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        env_file_path: "D:/project/apps/api/.env.local",
        setup_required: false,
        deepseek_configured: true,
        deepseek_api_base_url: "https://api.deepseek.com",
        deepseek_model: "deepseek-chat",
        task_generation_provider: "auto",
        retrieval_profile_provider: "auto",
        missing_required_settings: [],
      }),
    });

    const config = await updateRuntimeConfig({
      deepseek_api_key: "sk-test-123",
      deepseek_api_base_url: "https://api.deepseek.com",
      deepseek_model: "deepseek-chat",
    });

    expect(config.deepseek_configured).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/runtime-config",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          deepseek_api_key: "sk-test-123",
          deepseek_api_base_url: "https://api.deepseek.com",
          deepseek_model: "deepseek-chat",
        }),
      }),
    );
  });
});
