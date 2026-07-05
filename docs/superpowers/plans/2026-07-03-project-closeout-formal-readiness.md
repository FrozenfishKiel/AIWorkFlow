# Project Closeout Formal Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收掉当前仓库里会影响正式测试和上线判断的高优先级缺口，让正式验收围绕当前商品内容主链，而不是旧工作台壳或假交互。

**Architecture:** 这一轮不重做产品方向，只做收尾对齐。前端去掉误导性交互和旧原型入口；后端补齐正式方案要求的第 4 类固定电商资料；验收脚本与 acceptance 改成围绕 `/product-content` 主链验证正式流；旧 `/tasks` 与 `/knowledge` 路由保留兼容但不再作为正式对外文档入口。

**Tech Stack:** FastAPI, SQLModel, React, Vite, Vitest, pytest

---

## Task 1: 前端去掉误导性交互与旧原型入口

**Files:**
- Modify: `apps/web/src/prototype/StructuredSaasPrototype.tsx`
- Modify: `apps/web/vite.config.ts`
- Delete: `apps/web/redesign-prototype.html`
- Delete: `apps/web/src/prototype/main.tsx`
- Test: `apps/web/tests/unit/consoleLocalization.test.tsx`
- Test: `apps/web/tests/unit/prototypeLocalization.test.tsx`

- [ ] 去掉结果区无实际切换能力的 tab 交互
- [ ] 删除独立 `redesignPrototype` Vite 入口与对应 HTML / boot 文件
- [ ] 更新前端静态测试，确认不再暴露旧原型入口和误导性交互

## Task 2: 补齐固定电商资料底座

**Files:**
- Modify: `apps/api/app/services/default_ecommerce_knowledge.py`
- Add: `knowledge-base/02-curated-notes/ecommerce/商品资料模板.md`
- Test: `apps/api/tests/unit/test_default_ecommerce_knowledge_seed.py`

- [ ] 新增“商品资料模板”资料文件
- [ ] 把默认知识种子从 3 类补齐到正式方案要求的 4 类
- [ ] 更新单测验证资料底座完整性

## Task 3: 把正式 acceptance 切到当前商品内容主链

**Files:**
- Modify: `tests/acceptance/test_task_review_export_acceptance.py`
- Modify: `apps/api/app/api/routes_tasks.py`
- Modify: `apps/api/app/api/routes_knowledge.py`
- Modify: `apps/api/app/main.py`

- [ ] 改写 acceptance，使其围绕 `/product-content/jobs -> /exports -> artifact` 验证正式流
- [ ] 保留旧 `/tasks` 与 `/knowledge` 兼容能力，但不再作为正式 API 文档入口
- [ ] 把 API 标题改成当前正式产品口径

## Task 4: 完整验证与正式测试

**Files:**
- Verify only

- [ ] 运行 `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all`
- [ ] 启动本地 API / Web 正式入口，走一遍首页 -> 工作台 -> 生成 -> 导出用户流
- [ ] 记录正式测试结论和剩余风险
