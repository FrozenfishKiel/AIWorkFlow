# Structured SaaS 原型收口与一致性清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理原型中不符合已确认设计方向的模块与话术，并把首页与工作台页面继续收口到更克制、更成熟的中文 SaaS 呈现。

**Architecture:** 保持当前独立原型入口不变，只调整 `StructuredSaasPrototype` 的信息结构和页面文案；同步修正文档与现有应用中的残留命名，确保设计方向和工程表述一致。验证仍走仓库既有的 web 校验脚本。

**Tech Stack:** React 19、TypeScript、Vite、CSS、PowerShell 验证脚本

---

### Task 1: 收口原型首页信息结构

**Files:**
- Modify: `apps/web/src/prototype/StructuredSaasPrototype.tsx`
- Modify: `apps/web/src/prototype/structured-saas-prototype.css`

- [ ] **Step 1: 调整首页结构，移除用户明确不要的模块**

  把首页里的“结果可信 / 可信度说明 / 结果交付”相关模块与措辞删除，保留更克制的价值表达和首屏结果预览。

- [ ] **Step 2: 收紧首页文案**

  将首页文案改成全中文、偏成熟 SaaS 的表述，避免“流程解释”“系统可信度说明”“交付中心”之类半成品感较强的话术。

- [ ] **Step 3: 微调样式承接新的首页结构**

  删除不再使用的首页区块样式，并补足价值区块或预览区块的间距、网格与视觉权重，使页面在删除模块后仍然完整。

### Task 2: 收口工作台结果区与动作文案

**Files:**
- Modify: `apps/web/src/prototype/StructuredSaasPrototype.tsx`

- [ ] **Step 1: 调整工作台空态与结果区文案**

  保留“输入 + 结果”的主结构，但将结果区描述改为更直接的可编辑初稿表达，避免营销化或过程解释化措辞。

- [ ] **Step 2: 保留必要辅助信息但降低存在感**

  风险提醒与参考依据仍作为辅助信息存在，但不再与主结果并列成“可信度模块”，只作为轻量补充区域出现。

### Task 3: 修正文档与现有页面残留不一致

**Files:**
- Modify: `docs/superpowers/specs/2026-07-03-structured-saas-redesign-design.md`
- Modify: `apps/web/index.html`
- Modify: `apps/web/src/pages/ProductWorkspacePage.tsx`

- [ ] **Step 1: 更新设计文档**

  把设计文档中的“结果可信度说明”“结果交付”等结构描述改掉，确保文档和原型一致。

- [ ] **Step 2: 清理现有页面残留命名**

  修正应用标题与页面中残留的英文小标题，统一为全中文表述，避免正式界面出现中英混杂。

### Task 4: 运行验证并检查构建状态

**Files:**
- Verify: `scripts/qa/verify.ps1`

- [ ] **Step 1: 运行前端验证**

  Run: `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope web`

  Expected: Web 相关检查全部通过，原型入口继续可构建。

- [ ] **Step 2: 人工复核关键输出**

  确认 `redesign-prototype.html` 仍可访问，且页面中不再出现“结果可信 / 可信度说明 / 结果交付”等模块或措辞。
