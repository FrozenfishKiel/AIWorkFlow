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
            specifications: ["50ml", "SPF50+", "PA++++"],
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

  it("normalizes the formal product content job contract for the frontend", async () => {
    const { fetchProductContentJob } = await import("../../src/services/productContent");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: "job-2",
        status: "completed",
        current_stage: "completed",
        error_message: null,
        product: {
          name: "氨基酸净澈洁面乳",
          category: "个护清洁",
          specifications: ["150g", "氨基酸配方"],
          price_range: "79-99 元",
          core_selling_points: ["温和净润", "泡沫细腻"],
          target_audience: "18-35 岁女性",
          use_scenarios: ["日常洁面", "换季维稳"],
          promotion_notes: "夏季焕肤专题",
        },
        task_description: "生成电商卖点文案、详情页文案和小红书种草短文案。",
        product_brief: {
          summary: "这是一款强调温和清洁与舒缓肤感的洁面产品。",
          target_audience: "18-35 岁女性",
          use_scenarios: ["日常洁面", "换季维稳"],
          primary_value_points: ["温和净润", "泡沫细腻"],
        },
        selling_strategy: {
          primary_angle: "温和净润",
          supporting_angles: ["泡沫细腻", "清洁后不紧绷"],
          scenario_focus: ["日常洁面", "换季维稳"],
          expression_guardrails: ["避免功效夸大", "优先描述真实肤感"],
        },
        input_alerts: ["规格参数还可以补充更细。"],
        reference_context: [
          {
            source_id: "brand-tone-guide",
            title: "品牌语气规范",
            snippet: "强调真实肤感和日常体验。",
            reason: "当前任务更适合自然松弛表达。",
          },
        ],
        generated_content: {
          selling_points_copy: ["温和净润，清洁后不紧绷。"],
          detail_page_copy: "详情页围绕使用体验展开。",
          social_seed_copy: "最近在用这支洁面乳，泡沫很细。",
          risk_notes: ["避免使用过度功效承诺。"],
          applied_guidelines: ["品牌语气规范"],
        },
        created_at: "2026-07-03T00:00:00Z",
        updated_at: "2026-07-03T00:05:00Z",
      }),
    });

    const job = await fetchProductContentJob("job-2");

    expect(job.sellingStrategy?.primaryAngle).toBe("温和净润");
    expect(job.sellingStrategy?.supportingAngles).toEqual(["泡沫细腻", "清洁后不紧绷"]);
    expect(job.inputAlerts).toEqual(["规格参数还可以补充更细。"]);
    expect(job.referenceContext[0]?.sourceId).toBe("brand-tone-guide");
  });

  it("splits one-line product facts into multiple structured items", async () => {
    const { createProductContentJob } = await import("../../src/services/productContent");

    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        id: "job-3",
        status: "queued",
        current_stage: "queued",
        error_message: null,
        product: {
          name: "黑咖啡浓缩液",
          category: "冲调饮品",
          specifications: ["30ml*7条", "冷水即溶", "便携小袋装"],
          price_range: "39-49元",
          core_selling_points: ["冷水即溶", "0蔗糖", "便携提神"],
          target_audience: "通勤族",
          use_scenarios: ["早八通勤", "午后犯困", "出差随身"],
          promotion_notes: "夏季提神专题",
        },
        task_description: "生成三类商品内容初稿。",
        generated_content: null,
        reference_context: [],
        created_at: "2026-07-03T00:00:00Z",
        updated_at: "2026-07-03T00:00:00Z",
      }),
    });

    await createProductContentJob({
      name: "黑咖啡浓缩液",
      category: "冲调饮品",
      specificationsText: "30ml*7条 冷水即溶 便携小袋装",
      priceRange: "39-49元",
      coreSellingPointsText: "冷水即溶 0蔗糖 便携提神",
      targetAudience: "通勤族",
      useScenariosText: "早八通勤 午后犯困 出差随身",
      promotionNotes: "夏季提神专题",
      taskDescription: "生成三类商品内容初稿。",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/product-content/jobs",
      expect.objectContaining({
        body: JSON.stringify({
          product: {
            name: "黑咖啡浓缩液",
            category: "冲调饮品",
            specifications: ["30ml*7条", "冷水即溶", "便携小袋装"],
            price_range: "39-49元",
            core_selling_points: ["冷水即溶", "0蔗糖", "便携提神"],
            target_audience: "通勤族",
            use_scenarios: ["早八通勤", "午后犯困", "出差随身"],
            promotion_notes: "夏季提神专题",
          },
          task_description: "生成三类商品内容初稿。",
        }),
      }),
    );
  });
});
