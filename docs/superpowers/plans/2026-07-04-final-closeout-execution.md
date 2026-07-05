# Final Closeout Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/02-architecture/2026-07-04-最终收尾版技术方案.md` 把项目收成“官网首屏 + 工作台 + 生成依据证据层”的正式演示交付版，并补齐主链可证明性、失败分支和回归验证。

**Architecture:** 前端继续以 `apps/web/src/prototype/StructuredSaasPrototype.tsx` 为正式入口壳，但不再把“参考依据”简单堆在结果区，而是升级为单独的“生成依据”抽屉，集中展示系统理解、参考资料、卖点提炼和风险提示。后端继续复用现有 `/product-content` 主链，在已有 `product_brief / reference_context / generated_content` 基础上补出稳定的“卖点提炼”和“输入质量/失败提醒”契约，让前端证据层、主结果层和测试层围绕同一套对象工作。

**Tech Stack:** FastAPI, SQLModel, React, Vite, Vitest, pytest

---

## Task 1: 统一主链证据层契约

**Files:**
- Modify: `apps/api/app/schemas/product_content.py`
- Modify: `apps/api/app/api/routes_product_content.py`
- Modify: `apps/api/app/services/task_pipeline_service.py`
- Modify: `apps/api/app/services/generation_provider.py`
- Modify: `apps/web/src/types/productContent.ts`
- Modify: `apps/web/src/services/productContent.ts`
- Modify: `apps/web/src/prototype/prototypeContentAdapter.ts`
- Test: `apps/api/tests/unit/test_product_content_pipeline.py`
- Test: `apps/web/tests/unit/productContentService.test.ts`

- [ ] 先在后端单测里定义正式契约：任务结果除 `product_brief / reference_context / generated_content` 外，还必须稳定返回 `selling_strategy` 和 `input_alerts`
- [ ] 运行 `D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest apps/api/tests/unit/test_product_content_pipeline.py -q`，确认新增断言先失败
- [ ] 在主链里补齐“卖点提炼”和“弱输入提醒”生成逻辑，并通过 schema 和 route 暴露出去
- [ ] 在前端类型与服务层同步新字段，补一个面向 API 记录归一化的单测
- [ ] 重跑 API 单测与前端单测，确认前后端契约一致

## Task 2: 做成正式“生成依据”抽屉

**Files:**
- Modify: `apps/web/src/prototype/StructuredSaasPrototype.tsx`
- Modify: `apps/web/src/prototype/prototypeContentAdapter.ts`
- Modify: `apps/web/src/styles.css`
- Test: `apps/web/tests/unit/prototypeLocalization.test.tsx`
- Test: `apps/web/tests/unit/productContentResult.test.tsx`

- [ ] 先写前端单测，要求工作台结果区存在“查看生成依据”入口，并且抽屉只展示四块：系统理解、参考资料、卖点提炼、风险提示
- [ ] 运行 `npm --prefix apps/web run test -- --runInBand` 或仓库现有 web 校验命令，确认新断言先失败
- [ ] 在正式入口页面加入抽屉状态、打开关闭交互和四块证据内容映射
- [ ] 删除结果区里与最终方案冲突的“参考依据整块常驻展示”写法，保留结果主区只承载用户真正关心的初稿结果
- [ ] 重跑相关 Vitest，确认页面结构已符合“官网首屏 + 工作台 + 生成依据抽屉”

## Task 3: 补齐失败分支与恢复行为

**Files:**
- Modify: `apps/api/app/services/task_pipeline_service.py`
- Modify: `apps/web/src/pages/productWorkspaceState.ts`
- Modify: `apps/web/src/prototype/StructuredSaasPrototype.tsx`
- Test: `apps/api/tests/unit/test_product_content_pipeline.py`
- Test: `apps/web/tests/unit/productWorkspaceState.test.ts`

- [ ] 先加失败场景测试：弱输入时后端必须产出可见提醒；历史残留 job id 失效时前端必须清理并可恢复继续使用
- [ ] 运行对应 pytest / Vitest，确认新增场景先失败
- [ ] 在后端把弱输入、资料命中不足、卖点不足这三类提醒稳定写入 `input_alerts` / `risk_notes`
- [ ] 在前端把这些提醒接到工作台显性文案，不展示工程日志，不吞掉真实错误
- [ ] 重跑相关测试，确认失败分支既可见又不破坏主链

## Task 4: 固定回归样本并完成正式校验

**Files:**
- Modify: `tests/acceptance/test_task_review_export_acceptance.py`
- Modify: `tests/acceptance/conftest.py`
- Modify: `README.md`
- Modify: `apps/web/README.md`
- Verify only: `scripts/qa/verify.ps1`

- [ ] 把 acceptance 与说明文档明确收口到当前商品内容主链、生成依据和导出行为
- [ ] 保留至少一组固定商品样本，覆盖“生成三类文案 + 查看生成依据 + 导出”
- [ ] 运行 `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api`
- [ ] 运行 `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope web`
- [ ] 运行 `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all`

## 自检

- 规格覆盖
  - 已覆盖最终技术方案要求的正式页面结构、主链证据层、失败分支和固定回归验证
- Placeholder 扫描
  - 本计划未保留 “以后再补”“临时占位”“最低实现” 之类表述
- 一致性
  - 后续统一使用 `product_brief / reference_context / selling_strategy / generated_content / input_alerts` 这一套命名
