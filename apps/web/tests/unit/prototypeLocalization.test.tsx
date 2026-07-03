import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StructuredSaasPrototype } from "../../src/prototype/StructuredSaasPrototype";

describe("redesign prototype scope", () => {
  it("removes non-functional navigation and image-generation semantics", () => {
    const html = renderToStaticMarkup(<StructuredSaasPrototype />);

    expect(html).toContain("电商商品内容生产系统");
    expect(html).toContain("项目现有主流程");
    expect(html).toContain("生成商品内容初稿");
    expect(html).toContain("商品理解摘要");

    expect(html).not.toContain("解决方案");
    expect(html).not.toContain("应用场景");
    expect(html).not.toContain("使用方式");
    expect(html).not.toContain("资料底座");
    expect(html).not.toContain("导出记录");
    expect(html).not.toContain("当前套餐");
    expect(html).not.toContain("深受头部品牌信赖");
    expect(html).not.toContain("主图结果");
    expect(html).not.toContain("卖点图结果");
    expect(html).not.toContain("场景图结果");
    expect(html).not.toContain("详情页图结果");
  });
});
