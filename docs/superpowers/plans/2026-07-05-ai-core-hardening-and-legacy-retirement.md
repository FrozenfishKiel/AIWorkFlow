# AI Core Hardening And Legacy Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按最终收尾版技术方案，把旧 `/tasks` 公共链清干净，同时把商品内容主链的切分、检索、证据边界和默认真链运行方式做实。

**Architecture:** 正式对外入口只保留 `product-content` 主链，旧任务台路由不再暴露。知识库继续沿用现有 `KnowledgeDocument / KnowledgeChunk` 持久化模型，但把切分从粗段落拼接升级为结构感知切分，把检索从英语弱词面规则升级为适合中文商品资料的混合召回，并把“实际送进生成的证据”与“仅召回到的候选资料”明确分层持久化。

**Tech Stack:** FastAPI, SQLModel, pytest, React, Vite, Vitest, DeepSeek-compatible API

---

## 文件改造面

- 旧链与正式入口
  - `apps/api/app/main.py`
  - `apps/api/app/api/routes_tasks.py`
  - `apps/api/app/api/routes_product_content.py`
  - `apps/api/tests/integration/test_tasks_api.py`
  - `apps/api/tests/integration/test_product_content_api.py`
  - `apps/web/tests/unit/apiClient.test.ts`
- 检索与切分
  - `apps/api/app/services/knowledge_index_service.py`
  - `apps/api/app/services/retrieval_service.py`
  - `apps/api/app/services/retrieval_profile_provider.py`
  - `apps/api/app/services/default_ecommerce_knowledge.py`
  - `apps/api/tests/unit/test_knowledge_index_service.py`
  - `apps/api/tests/unit/test_retrieval_service.py`
  - `apps/api/tests/unit/test_retrieval_service_diagnostics.py`
  - `apps/api/tests/evaluation/test_retrieval_regression.py`
- 证据边界与生成约束
  - `apps/api/app/services/task_pipeline_service.py`
  - `apps/api/app/services/generation_provider.py`
  - `apps/api/app/schemas/product_content.py`
  - `apps/api/tests/unit/test_product_content_pipeline.py`
  - `apps/api/tests/integration/test_product_content_api.py`
- 运行默认值与文档
  - `apps/api/.env.local`
  - `README.md`
  - `apps/api/README.md`

## Task 1: 退役旧 `/tasks` 公共链

**Files:**
- Modify: `apps/api/tests/integration/test_tasks_api.py`
- Modify: `apps/api/tests/integration/test_product_content_api.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/api/routes_tasks.py`
- Modify: `apps/api/app/api/routes_product_content.py`
- Test: `apps/web/tests/unit/apiClient.test.ts`

- [ ] **Step 1: 先写失败测试**
  - 旧 `/tasks` 公开接口应返回 `404`
  - 正式鉴权、导出、审计日志能力应仍可从正式入口验证
- [ ] **Step 2: 运行相关 pytest / vitest，确认红测来自旧公共链仍被暴露**
- [ ] **Step 3: 移除 `main.py` 中的旧 router 暴露，把需要保留的审计能力迁到 `product-content` 正式路由**
- [ ] **Step 4: 重跑对应测试，确认正式入口可用且旧链不再对外**

## Task 2: 升级知识库切分与中文检索

**Files:**
- Modify: `apps/api/tests/unit/test_knowledge_index_service.py`
- Modify: `apps/api/tests/unit/test_retrieval_service.py`
- Modify: `apps/api/tests/unit/test_retrieval_service_diagnostics.py`
- Modify: `apps/api/tests/evaluation/test_retrieval_regression.py`
- Modify: `apps/api/app/services/knowledge_index_service.py`
- Modify: `apps/api/app/services/retrieval_service.py`
- Modify: `apps/api/app/services/retrieval_profile_provider.py`

- [ ] **Step 1: 先写失败测试**
  - 标题 / 小节 / 列表能切成多个结构化 chunk
  - 中文商品查询不会因为旧英文 token 规则而失真
  - 召回理由要是人能看懂的命中说明，而不是原始打分日志
- [ ] **Step 2: 运行相关测试，确认当前实现确实在这些点上失败**
- [ ] **Step 3: 实现结构感知切分、中文词面特征和混合排序改造**
- [ ] **Step 4: 重跑单测与回归测试，确认召回质量和解释质量提升**

## Task 3: 闭合证据边界与弱检索约束

**Files:**
- Modify: `apps/api/tests/unit/test_product_content_pipeline.py`
- Modify: `apps/api/tests/integration/test_product_content_api.py`
- Modify: `apps/api/app/services/task_pipeline_service.py`
- Modify: `apps/api/app/services/generation_provider.py`
- Modify: `apps/api/app/schemas/product_content.py`

- [ ] **Step 1: 先写失败测试**
  - 商品主链要区分“召回候选资料”和“实际选中进生成的证据”
  - 弱命中时结果必须进入保守生成与风险提醒，不得把排序理由串进表达约束
- [ ] **Step 2: 运行相关 pytest，确认当前证据边界和 guardrail 行为失败**
- [ ] **Step 3: 实现候选证据筛选、稳定快照冻结、弱检索约束注入生成上下文**
- [ ] **Step 4: 重跑测试，确认正式主链真正消费选中证据**

## Task 4: 切回真链优先默认值并补文档

**Files:**
- Modify: `apps/api/.env.local`
- Modify: `README.md`
- Modify: `apps/api/README.md`

- [ ] **Step 1: 把本地默认 provider 从 deterministic 改成真链优先自动模式**
- [ ] **Step 2: 更新运行文档，明确“测试可指定 deterministic，日常联调默认走真实 provider”**
- [ ] **Step 3: 跑 `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api`**
- [ ] **Step 4: 跑 `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope web`**
- [ ] **Step 5: 跑 `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all`**
- [ ] **Step 6: 用真实商品输入做多轮手测，检查结果差异、按钮交互和导出是否正常**

## 自检

- 规格覆盖
  - 旧公共链退役、主链证据化、切分检索强化、弱输入/弱命中约束、真链默认运行都已纳入。
- Placeholder 扫描
  - 无 TBD / TODO 占位，所有任务都指向具体文件和验证面。
- 一致性
  - 后续统一使用“参考候选资料 / 选中证据 / 卖点中间层 / 风险提醒 / 导出交付”这套命名。
