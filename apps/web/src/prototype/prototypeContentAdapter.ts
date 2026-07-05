import type { ProductContentJobDetail, ProductInputFormValues } from "../types/productContent";

export type PrototypeFormState = {
  name: string;
  category: string;
  specifications: string;
  priceRange: string;
  feature: string;
  audience: string;
  scenarios: string;
  promotion: string;
  taskDescription: string;
};

export type PrototypeResultViewModel = {
  productBriefSummary: string;
  targetAudience: string;
  useScenarios: string[];
  primaryValuePoints: string[];
  sellingStrategy: {
    primaryAngle: string;
    supportingAngles: string[];
    scenarioFocus: string[];
    expressionGuardrails: string[];
  };
  inputAlerts: string[];
  sellingPoints: string[];
  detailPageCopy: string;
  socialSeedCopy: string;
  riskNotes: string[];
  references: Array<{
    title: string;
    reason: string;
    snippet: string;
  }>;
};

export function toProductInputFormValues(formState: PrototypeFormState): ProductInputFormValues {
  return {
    name: formState.name,
    category: formState.category,
    specificationsText: formState.specifications,
    priceRange: formState.priceRange,
    coreSellingPointsText: formState.feature,
    targetAudience: formState.audience,
    useScenariosText: formState.scenarios,
    promotionNotes: formState.promotion,
    taskDescription: formState.taskDescription,
  };
}

export function toPrototypeFormState(job: ProductContentJobDetail): PrototypeFormState {
  return {
    name: job.product.name,
    category: job.product.category,
    specifications: job.product.specifications.join("\n"),
    priceRange: job.product.priceRange || "",
    feature: job.product.coreSellingPoints.join("\n"),
    audience: job.product.targetAudience || "",
    scenarios: job.product.useScenarios.join("\n"),
    promotion: job.product.promotionNotes || "",
    taskDescription: job.taskDescription,
  };
}

export function toPrototypeResultViewModel(job: ProductContentJobDetail): PrototypeResultViewModel {
  return {
    productBriefSummary: job.productBrief?.summary || "当前还没有生成商品理解摘要。",
    targetAudience: job.productBrief?.targetAudience || job.product.targetAudience || "未填写",
    useScenarios: job.productBrief?.useScenarios.length
      ? job.productBrief.useScenarios
      : job.product.useScenarios,
    primaryValuePoints: job.productBrief?.primaryValuePoints.length
      ? job.productBrief.primaryValuePoints
      : job.product.coreSellingPoints,
    sellingStrategy: {
      primaryAngle:
        job.sellingStrategy?.primaryAngle || job.productBrief?.primaryValuePoints[0] || job.product.coreSellingPoints[0] || "待系统提炼",
      supportingAngles:
        job.sellingStrategy?.supportingAngles.length
          ? job.sellingStrategy.supportingAngles
          : job.productBrief?.primaryValuePoints.slice(1) || job.product.coreSellingPoints.slice(1),
      scenarioFocus:
        job.sellingStrategy?.scenarioFocus.length
          ? job.sellingStrategy.scenarioFocus
          : job.productBrief?.useScenarios.length
            ? job.productBrief.useScenarios
            : job.product.useScenarios,
      expressionGuardrails: job.sellingStrategy?.expressionGuardrails || [],
    },
    inputAlerts: job.inputAlerts,
    sellingPoints: job.generatedContent?.sellingPointsCopy || [],
    detailPageCopy: job.generatedContent?.detailPageCopy || "",
    socialSeedCopy: job.generatedContent?.socialSeedCopy || "",
    riskNotes: job.generatedContent?.riskNotes || [],
    references: job.referenceContext.map((item) => ({
      title: item.title,
      reason: item.reason,
      snippet: item.snippet,
    })),
  };
}
