import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AuthPanel } from "../../src/features/auth/AuthPanel";
import { ProductWorkspacePage } from "../../src/pages/ProductWorkspacePage";

describe("product workspace localization", () => {
  it("renders the main workspace as a Chinese product page instead of a task console", () => {
    const pageHtml = renderToStaticMarkup(<ProductWorkspacePage />);

    expect(pageHtml).toContain("电商商品内容生产系统");
    expect(pageHtml).toContain("输入商品任务");
    expect(pageHtml).toContain("当前结果");
    expect(pageHtml).toContain("商品内容工作台");
    expect(pageHtml).not.toContain("这次会得到什么");
    expect(pageHtml).not.toContain("高质量初稿，不是最终发布稿");
    expect(pageHtml).not.toContain("系统这次会怎么处理");
    expect(pageHtml).not.toContain("适合怎么输入");
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
