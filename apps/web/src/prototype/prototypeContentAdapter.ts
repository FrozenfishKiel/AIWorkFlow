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
