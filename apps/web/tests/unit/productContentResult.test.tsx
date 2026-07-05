import { describe, expect, it, vi } from "vitest";
import { isValidElement, type ReactNode } from "react";

import { ProductContentResult } from "../../src/features/product-content/ProductContentResult";
import type { ProductContentJobDetail } from "../../src/types/productContent";

function flattenText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    return node.map((item) => flattenText(item)).join("");
  }

  if (isValidElement(node)) {
    return flattenText(node.props.children);
  }

  return "";
}

function findButtonByText(node: ReactNode, text: string): { props: { onClick?: () => void } } | null {
  if (!node) {
    return null;
  }

  if (Array.isArray(node)) {
    for (const child of node) {
      const match = findButtonByText(child, text);
      if (match) {
        return match;
      }
    }
    return null;
  }

  if (!isValidElement(node)) {
    return null;
  }

  if (node.type === "button" && flattenText(node.props.children).includes(text)) {
    return node.props;
  }

  return findButtonByText(node.props.children, text);
}

describe("ProductContentResult", () => {
  it("renders the three draft sections, references, and export actions", () => {
    const onExportMarkdown = vi.fn();
    const onExportStructuredText = vi.fn();
    const onDownloadExport = vi.fn();
    const onOpenEvidence = vi.fn();

    const tree = ProductContentResult({
      job: {
        id: "job-1",
        status: "completed",
        currentStage: "completed",
        errorMessage: null,
        product: {
          name: "清透防晒霜",
          category: "护肤",
          specifications: ["50ml", "SPF50+ PA++++"],
          priceRange: "89-129元",
          coreSellingPoints: ["清爽不搓泥", "通勤补涂方便"],
          targetAudience: "通勤女生",
          useScenarios: ["夏季通勤", "户外补涂"],
          promotionNotes: "618 第二件半价",
        },
        taskDescription: "生成电商卖点、详情页和小红书种草短文案。",
        productBrief: {
          summary: "这是一款适合通勤场景的轻透防晒产品。",
          targetAudience: "通勤女生",
          useScenarios: ["夏季通勤", "户外补涂"],
          primaryValuePoints: ["清爽不搓泥", "补涂方便"],
        },
        sellingStrategy: {
          primaryAngle: "清爽不搓泥",
          supportingAngles: ["补涂方便", "高倍防护"],
          scenarioFocus: ["夏季通勤", "户外补涂"],
          expressionGuardrails: ["避免绝对化表达", "优先强调真实肤感"],
        },
        inputAlerts: [],
        referenceContext: [
          {
            sourceId: "brand-tone-guide",
            title: "品牌语气规范",
            snippet: "强调真实体验，不要使用绝对化承诺。",
            reason: "约束表达方式。",
          },
        ],
        generatedContent: {
          sellingPointsCopy: ["清爽不搓泥，补涂更轻松。"],
          detailPageCopy: "详情页重点突出轻透肤感和高倍防护。",
          socialSeedCopy: "通勤补涂不搓泥，这支我会一直放包里。",
          riskNotes: ["避免使用绝对化防晒承诺。"],
          appliedGuidelines: ["品牌语气规范"],
        },
        createdAt: "2026-07-03T00:00:00Z",
        updatedAt: "2026-07-03T00:05:00Z",
      } satisfies ProductContentJobDetail,
      exportJob: {
        id: "export-1",
        status: "completed",
        exportType: "markdown",
        filePath: ".runtime/exports/export-1.md",
      },
      onOpenEvidence,
      onExportMarkdown,
      onExportStructuredText,
      onDownloadExport,
    });

    const text = flattenText(tree);

    expect(text).toContain("电商卖点文案");
    expect(text).toContain("商品详情页文案");
    expect(text).toContain("小红书 / 种草短文案");
    expect(text).toContain("生成依据");
    expect(text).toContain("风险提醒");
    expect(text).toContain("清爽不搓泥，补涂更轻松。");
    expect(text).not.toContain("品牌语气规范");

    findButtonByText(tree, "查看生成依据")?.onClick?.();
    findButtonByText(tree, "导出 Markdown")?.onClick?.();
    findButtonByText(tree, "导出结构化文本")?.onClick?.();
    findButtonByText(tree, "下载导出文件")?.onClick?.();

    expect(onOpenEvidence).toHaveBeenCalledTimes(1);
    expect(onExportMarkdown).toHaveBeenCalledTimes(1);
    expect(onExportStructuredText).toHaveBeenCalledTimes(1);
    expect(onDownloadExport).toHaveBeenCalledTimes(1);
  });

  it("shows a simple progress hint while the current generation job is still running", () => {
    const tree = ProductContentResult({
      job: {
        id: "job-pending",
        status: "generating",
        currentStage: "generating",
        errorMessage: null,
        product: {
          name: "清透防晒霜",
          category: "护肤",
          specifications: [],
          priceRange: null,
          coreSellingPoints: [],
          targetAudience: null,
          useScenarios: [],
          promotionNotes: null,
        },
        taskDescription: "生成三类初稿。",
        productBrief: null,
        sellingStrategy: null,
        inputAlerts: [],
        referenceContext: [],
        generatedContent: null,
        createdAt: "2026-07-03T00:00:00Z",
        updatedAt: "2026-07-03T00:01:00Z",
      } satisfies ProductContentJobDetail,
    });

    expect(flattenText(tree)).toContain("正在整理本轮内容草稿");
  });
});
