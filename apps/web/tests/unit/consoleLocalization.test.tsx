import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AuthPanel } from "../../src/features/auth/AuthPanel";
import { ProductWorkspacePage } from "../../src/pages/ProductWorkspacePage";

describe("product workspace localization", () => {
  it("renders the official root entry without preview-only homepage scaffolding", () => {
    const pageHtml = renderToStaticMarkup(<ProductWorkspacePage />);

    expect(pageHtml).toContain("\u7535\u5546\u5546\u54c1\u5185\u5bb9\u751f\u4ea7\u7cfb\u7edf");
    expect(pageHtml).toContain("AI \u9a71\u52a8\u7684\u7535\u5546\u5185\u5bb9\u751f\u4ea7\u5f15\u64ce");
    expect(pageHtml).toContain("\u8ba9\u5546\u54c1\u5185\u5bb9\u8d77\u7a3f\uff0c\u4ece\u96f6\u6563\u7ecf\u9a8c\u53d8\u6210\u7a33\u5b9a\u6d41\u7a0b");
    expect(pageHtml).toContain("\u5148\u7406\u89e3\u5546\u54c1\uff0c\u518d\u7ec4\u7ec7\u5185\u5bb9");
    expect(pageHtml).not.toContain("\u9879\u76ee\u73b0\u6709\u4e3b\u6d41\u7a0b");
    expect(pageHtml).not.toContain("\u5b57\u6bb5\u7ed3\u6784\u9884\u89c8");
    expect(pageHtml).not.toContain("\u7ed3\u679c\u7ed3\u6784\u9884\u89c8");
    expect(pageHtml).not.toContain("\u67e5\u770b\u5de5\u4f5c\u53f0");
    expect(pageHtml).not.toContain("Task list");
    expect(pageHtml).not.toContain("\u4efb\u52a1\u5217\u8868");
  });

  it("renders the password login panel in Chinese", () => {
    const authHtml = renderToStaticMarkup(
      <AuthPanel authMode="password_login" onSubmit={() => undefined} />,
    );

    expect(authHtml).toContain("\u64cd\u4f5c\u8005\u767b\u5f55");
    expect(authHtml).toContain("\u7528\u6237\u540d");
    expect(authHtml).toContain("\u5bc6\u7801");
  });
});
