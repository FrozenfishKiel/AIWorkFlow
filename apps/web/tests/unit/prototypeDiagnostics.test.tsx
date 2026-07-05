import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DiagnosticsDrawer } from "../../src/prototype/StructuredSaasPrototype";
import type { ExportJobRecord } from "../../src/types/export";
import type { ProductContentAuditLog, ProductContentJobDetail } from "../../src/types/productContent";

describe("prototype diagnostics drawer", () => {
  it("renders provider, retrieval, export, and failure diagnostics in the hidden backend surface", () => {
    const job = {
      id: "job-1",
      status: "failed",
      currentStage: "generating",
      errorMessage: "模型输出偏离商品事实，已终止当前任务。",
      product: {
        name: "便携挂脖小风扇",
        category: "便携小家电",
        specifications: ["三档风力", "Type-C充电"],
        priceRange: "59-89元",
        coreSellingPoints: ["解放双手", "轻量不压脖"],
        targetAudience: "通勤族和学生党",
        useScenarios: ["地铁通勤", "排队等车"],
        promotionNotes: "夏季清凉专场",
      },
      taskDescription: "生成详情页和种草短文案。",
      productBrief: null,
      sellingStrategy: null,
      inputAlerts: [],
      referenceContext: [],
      retrievalCandidates: [
        {
          sourceId: "fact-card",
          title: "便携挂脖小风扇事实卡",
          snippet: "强调解放双手和日常通勤场景。",
          reason: "命中商品事实卡。",
          rank: 1,
          score: 12.4,
          selected: true,
          matchedTerms: ["解放双手", "通勤"],
          matchedPhrases: ["通勤场景"],
          visibleText: "便携挂脖小风扇事实卡\n强调解放双手和日常通勤场景。",
        },
      ],
      contextSummary: {},
      diagnostics: {
        generationProvider: "deepseek",
        retrievalProvider: "deepseek-retrieval-profile",
        retrievalQuery: "商品 便携挂脖小风扇\n内容目标 种草 详情页",
        retrievalTopKRequested: 4,
        retrievalTopKEffective: 1,
        candidateHitCount: 1,
        selectedHitCount: 1,
        selectedSourceIds: ["fact-card"],
        selectedTitles: ["便携挂脖小风扇事实卡"],
        weakRetrieval: false,
        duplicateHitsRemoved: 0,
        failureStage: "generating",
        failureReason: "模型输出偏离商品事实，已终止当前任务。",
      },
      processingTrace: ["Built structured understanding.", "Retrieved 1 visible knowledge hit."],
      generatedContent: null,
      createdAt: "2026-07-05T00:00:00Z",
      updatedAt: "2026-07-05T00:05:00Z",
    } satisfies ProductContentJobDetail;

    const auditLogs = [
      {
        id: "audit-1",
        taskId: "job-1",
        exportJobId: null,
        eventType: "pipeline_failed",
        outcome: "failure",
        summary: "Pipeline failed before a stable result could be persisted.",
        details: { failure_reason: "模型输出偏离商品事实，已终止当前任务。" },
        createdAt: "2026-07-05T00:05:00Z",
      },
    ] satisfies ProductContentAuditLog[];

    const exportJobs = [
      {
        id: "export-1",
        task_id: "job-1",
        export_type: "markdown",
        status: "failed",
        error_message: "artifact path missing",
        file_path: null,
        created_at: "2026-07-05T00:06:00Z",
        updated_at: "2026-07-05T00:06:10Z",
      },
    ] satisfies ExportJobRecord[];

    const html = renderToStaticMarkup(
      <DiagnosticsDrawer
        job={job}
        open={true}
        isLoading={false}
        auditLogs={auditLogs}
        exportJobs={exportJobs}
        onClose={() => undefined}
      />,
    );

    expect(html).toContain("诊断后台");
    expect(html).toContain("生成 provider");
    expect(html).toContain("deepseek");
    expect(html).toContain("检索 provider");
    expect(html).toContain("召回候选");
    expect(html).toContain("便携挂脖小风扇事实卡");
    expect(html).toContain("导出状态");
    expect(html).toContain("artifact path missing");
    expect(html).toContain("审计时间线");
    expect(html).toContain("pipeline_failed");
    expect(html).toContain("失败原因");
  });
});
