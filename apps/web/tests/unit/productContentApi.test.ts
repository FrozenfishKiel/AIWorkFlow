import { afterEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

afterEach(() => {
  fetchMock.mockReset();
  vi.resetModules();
});

describe("product content api", () => {
  it("posts normalized product content payload to the new product-content endpoint", async () => {
    const { createProductContentJob } = await import("../../src/services/productContent");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        id: "job-1",
        status: "queued",
        current_stage: "queued",
        error_message: null,
        product: {
          name: "清透防晒霜",
          category: "护肤",
          specifications: ["50ml", "SPF50+ PA++++"],
          price_range: "89-129元",
          core_selling_points: ["清爽不搓泥", "通勤补涂方便"],
          target_audience: "通勤女生",
          use_scenarios: ["夏季通勤", "户外补涂"],
          promotion_notes: "618 第二件半价",
        },
        task_description: "生成电商卖点、详情页和小红书种草短文案。",
        generated_content: null,
        reference_context: [],
        created_at: "2026-07-03T00:00:00Z",
        updated_at: "2026-07-03T00:00:00Z",
      }),
    });

    const jobId = await createProductContentJob({
      name: "清透防晒霜",
      category: "护肤",
      specificationsText: "50ml\nSPF50+ PA++++",
      priceRange: "89-129元",
      coreSellingPointsText: "清爽不搓泥\n通勤补涂方便",
      targetAudience: "通勤女生",
      useScenariosText: "夏季通勤\n户外补涂",
      promotionNotes: "618 第二件半价",
      taskDescription: "生成电商卖点、详情页和小红书种草短文案。",
    });

    expect(jobId).toBe("job-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/product-content/jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          product: {
            name: "清透防晒霜",
            category: "护肤",
            specifications: ["50ml", "SPF50+ PA++++"],
            price_range: "89-129元",
            core_selling_points: ["清爽不搓泥", "通勤补涂方便"],
            target_audience: "通勤女生",
            use_scenarios: ["夏季通勤", "户外补涂"],
            promotion_notes: "618 第二件半价",
          },
          task_description: "生成电商卖点、详情页和小红书种草短文案。",
        }),
      }),
    );
  });
});
