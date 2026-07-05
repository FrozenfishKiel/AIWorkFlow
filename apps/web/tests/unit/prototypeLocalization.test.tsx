import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EvidenceDrawer, StructuredSaasPrototype } from "../../src/prototype/StructuredSaasPrototype";
import type { ProductContentJobDetail } from "../../src/types/productContent";

describe("redesign prototype scope", () => {
  it("keeps the homepage focused on formal product messaging instead of preview scaffolding", () => {
    const html = renderToStaticMarkup(<StructuredSaasPrototype />);

    expect(html).toContain("\u7535\u5546\u5546\u54c1\u5185\u5bb9\u751f\u4ea7\u7cfb\u7edf");
    expect(html).toContain("\u7ed3\u679c\u9884\u89c8");
    expect(html).toContain("\u5546\u54c1\u7406\u89e3\u6458\u8981");
    expect(html).not.toContain("\u9879\u76ee\u73b0\u6709\u4e3b\u6d41\u7a0b");
    expect(html).not.toContain("\u5b57\u6bb5\u7ed3\u6784\u9884\u89c8");
    expect(html).not.toContain("\u7ed3\u679c\u7ed3\u6784\u9884\u89c8");
    expect(html).not.toContain("\u67e5\u770b\u5de5\u4f5c\u53f0");
  });

  it("renders the evidence drawer as four formal proof sections", () => {
    const html = renderToStaticMarkup(
      <EvidenceDrawer
        open={true}
        onClose={() => undefined}
        job={{
          id: "job-1",
          status: "completed",
          currentStage: "completed",
          errorMessage: null,
          product: {
            name: "\u6c28\u57fa\u9178\u51c0\u6f88\u6d01\u9762\u4e73",
            category: "\u4e2a\u62a4\u6e05\u6d01",
            specifications: ["150g", "\u6c28\u57fa\u9178\u914d\u65b9"],
            priceRange: "79-99 \u5143",
            coreSellingPoints: ["\u6e29\u548c\u51c0\u6da6", "\u6ce1\u6cab\u7ec6\u817b"],
            targetAudience: "18-35 \u5c81\u5973\u6027",
            useScenarios: ["\u65e5\u5e38\u6d01\u9762", "\u6362\u5b63\u7ef4\u7a33"],
            promotionNotes: "\u590f\u5b63\u7115\u80a4\u4e13\u9898",
          },
          taskDescription:
            "\u751f\u6210\u7535\u5546\u5356\u70b9\u6587\u6848\u3001\u8be6\u60c5\u9875\u6587\u6848\u548c\u5c0f\u7ea2\u4e66\u79cd\u8349\u77ed\u6587\u6848\u3002",
          productBrief: {
            summary:
              "\u8fd9\u662f\u4e00\u6b3e\u5f3a\u8c03\u6e29\u548c\u6e05\u6d01\u4e0e\u8212\u7f13\u80a4\u611f\u7684\u6d01\u9762\u4ea7\u54c1\u3002",
            targetAudience: "18-35 \u5c81\u5973\u6027",
            useScenarios: ["\u65e5\u5e38\u6d01\u9762", "\u6362\u5b63\u7ef4\u7a33"],
            primaryValuePoints: ["\u6e29\u548c\u51c0\u6da6", "\u6ce1\u6cab\u7ec6\u817b"],
          },
          sellingStrategy: {
            primaryAngle: "\u6e29\u548c\u51c0\u6da6",
            supportingAngles: ["\u6ce1\u6cab\u7ec6\u817b", "\u6e05\u6d01\u540e\u4e0d\u7d27\u7ef7"],
            scenarioFocus: ["\u65e5\u5e38\u6d01\u9762", "\u6362\u5b63\u7ef4\u7a33"],
            expressionGuardrails: [
              "\u5f3a\u8c03\u771f\u5b9e\u80a4\u611f",
              "\u907f\u514d\u8fc7\u5ea6\u529f\u6548\u627f\u8bfa",
            ],
          },
          inputAlerts: ["\u89c4\u683c\u53c2\u6570\u8fd8\u53ef\u4ee5\u8865\u5145\u66f4\u7ec6\u3002"],
          referenceContext: [
            {
              sourceId: "brand-tone-guide",
              title: "\u54c1\u724c\u8bed\u6c14\u89c4\u8303",
              snippet: "\u5f3a\u8c03\u771f\u5b9e\u80a4\u611f\u548c\u65e5\u5e38\u4f53\u9a8c\u3002",
              reason: "\u5f53\u524d\u4efb\u52a1\u66f4\u9002\u5408\u81ea\u7136\u677e\u5f1b\u8868\u8fbe\u3002",
            },
          ],
          generatedContent: {
            sellingPointsCopy: ["\u6e29\u548c\u51c0\u6da6\uff0c\u6e05\u6d01\u540e\u4e0d\u7d27\u7ef7\u3002"],
            detailPageCopy: "\u8be6\u60c5\u9875\u56f4\u7ed5\u4f7f\u7528\u4f53\u9a8c\u5c55\u5f00\u3002",
            socialSeedCopy: "\u6700\u8fd1\u5728\u7528\u8fd9\u652f\u6d01\u9762\u4e73\uff0c\u6ce1\u6cab\u5f88\u7ec6\u3002",
            riskNotes: ["\u907f\u514d\u4f7f\u7528\u8fc7\u5ea6\u529f\u6548\u627f\u8bfa\u3002"],
            appliedGuidelines: ["\u54c1\u724c\u8bed\u6c14\u89c4\u8303"],
          },
          createdAt: "2026-07-03T00:00:00Z",
          updatedAt: "2026-07-03T00:05:00Z",
        } satisfies ProductContentJobDetail}
      />,
    );

    expect(html).toContain("\u751f\u6210\u4f9d\u636e");
    expect(html).toContain("\u7cfb\u7edf\u7406\u89e3");
    expect(html).toContain("\u53c2\u8003\u8d44\u6599");
    expect(html).toContain("\u5356\u70b9\u63d0\u70bc");
    expect(html).toContain("\u98ce\u9669\u63d0\u793a");
    expect(html).not.toContain("\u7535\u5546\u5356\u70b9\u6587\u6848");
  });
});
