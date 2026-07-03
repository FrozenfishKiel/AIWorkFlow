import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AuthPanel } from "../../src/features/auth/AuthPanel";
import { ProductWorkspacePage } from "../../src/pages/ProductWorkspacePage";

describe("product workspace localization", () => {
  it("renders the official root entry as the new homepage plus workspace experience", () => {
    const pageHtml = renderToStaticMarkup(<ProductWorkspacePage />);

    expect(pageHtml).toContain("电商商品内容生产系统");
    expect(pageHtml).toContain("AI 驱动的电商内容生产引擎");
    expect(pageHtml).toContain("让商品内容起稿，从零散经验变成稳定流程");
    expect(pageHtml).toContain("项目现有主流程");
    expect(pageHtml).toContain("从商品任务输入，到可继续编辑的内容结果");
    expect(pageHtml).toContain("输入商品任务");
    expect(pageHtml).toContain("当前结果");
    expect(pageHtml).not.toContain("商品内容工作台");
    expect(pageHtml).not.toContain(">登录<");
    expect(pageHtml).not.toContain("Task list");
    expect(pageHtml).not.toContain("任务列表");
  });

  it("renders the password login panel in Chinese", () => {
    const authHtml = renderToStaticMarkup(
      <AuthPanel authMode="password_login" onSubmit={() => undefined} />,
    );

    expect(authHtml).toContain("操作者登录");
    expect(authHtml).toContain("用户名");
    expect(authHtml).toContain("密码");
  });
});
