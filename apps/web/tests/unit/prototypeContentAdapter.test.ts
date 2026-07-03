import { describe, expect, it } from "vitest";

import { toProductInputFormValues, toPrototypeResultViewModel } from "../../src/prototype/prototypeContentAdapter";
import type { ProductContentJobDetail } from "../../src/types/productContent";

describe("prototype content adapter", () => {
  it("maps prototype form values into the existing product content API input contract", () => {
    const result = toProductInputFormValues({
      name: "氨基酸净澈洁面乳",
      category: "个护清洁",
      specifications: "150g\n氨基酸配方\n敏感肌可用",
      priceRange: "79-99 元",
      feature: "温和净润\n泡沫细腻\n清洁后不紧绷",
      audience: "18-35 岁女性",
      scenarios: "日常洁面\n换季维稳",
      promotion: "夏季焕肤专题",
      taskDescription: "生成电商卖点文案、详情页文案和小红书种草短文案。",
    });

    expect(result).toEqual({
      name: "氨基酸净澈洁面乳",
      category: "个护清洁",
      specificationsText: "150g\n氨基酸配方\n敏感肌可用",
      priceRange: "79-99 元",
      coreSellingPointsText: "温和净润\n泡沫细腻\n清洁后不紧绷",
      targetAudience: "18-35 岁女性",
      useScenariosText: "日常洁面\n换季维稳",
      promotionNotes: "夏季焕肤专题",
      taskDescription: "生成电商卖点文案、详情页文案和小红书种草短文案。",
    });
  });

  it("builds text-first result cards from the real job detail contract", () => {
    const viewModel = toPrototypeResultViewModel({
      id: "job-1",
      status: "completed",
      currentStage: "completed",
      errorMessage: null,
      product: {
        name: "氨基酸净澈洁面乳",
        category: "个护清洁",
        specifications: ["150g", "氨基酸配方"],
        priceRange: "79-99 元",
        coreSellingPoints: ["温和净润", "泡沫细腻"],
        targetAudience: "18-35 岁女性",
        useScenarios: ["日常洁面", "换季维稳"],
        promotionNotes: "夏季焕肤专题",
      },
      taskDescription: "生成电商卖点文案、详情页文案和小红书种草短文案。",
      productBrief: {
        summary: "这是一款强调温和清洁与舒缓肤感的洁面产品。",
        targetAudience: "18-35 岁女性",
        useScenarios: ["日常洁面", "换季维稳"],
        primaryValuePoints: ["温和净润", "泡沫细腻"],
      },
      referenceContext: [
        {
          sourceId: "brand-tone-guide",
          title: "品牌语气规范",
          snippet: "强调真实肤感和日常体验。",
          reason: "当前任务更适合自然松弛表达。",
        },
      ],
      generatedContent: {
        sellingPointsCopy: ["温和净润，清洁后不紧绷。"],
        detailPageCopy: "详情页围绕使用体验展开。",
        socialSeedCopy: "最近在用这支洁面乳，泡沫很细。",
        riskNotes: ["避免使用过度功效承诺。"],
        appliedGuidelines: ["品牌语气规范"],
      },
      createdAt: "2026-07-03T00:00:00Z",
      updatedAt: "2026-07-03T00:05:00Z",
    } satisfies ProductContentJobDetail);

    expect(viewModel.productBriefSummary).toContain("温和清洁");
    expect(viewModel.sellingPoints).toEqual(["温和净润，清洁后不紧绷。"]);
    expect(viewModel.detailPageCopy).toContain("详情页");
    expect(viewModel.socialSeedCopy).toContain("泡沫很细");
    expect(viewModel.riskNotes).toEqual(["避免使用过度功效承诺。"]);
    expect(viewModel.references[0]).toEqual({
      title: "品牌语气规范",
      reason: "当前任务更适合自然松弛表达。",
      snippet: "强调真实肤感和日常体验。",
    });
  });
});
