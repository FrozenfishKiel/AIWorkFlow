# AI Core Two-Part Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or equivalent Harness discipline. Keep scope tight, test after each phase, and avoid placeholder work.

**Goal:** 先把 AI 应用开发内核做实，再把系统级证据与统一测试补齐，避免“能演示但证明不了”。

## Part 1: 内核改造

**目标**
- 让知识库不再只命中通用写作规则，而是能命中更像商品事实/类目事实的资料。
- 让检索 query、chunk 粒度、索引重建和召回增强真正服务主链。
- 让当前主链的“命中什么、为什么命中、选中了什么”开始具备可诊断性。

**范围**
- 增补 `knowledge-base/02-curated-notes/ecommerce/` 的事实型知识卡与类目卡。
- 调整默认 `ecommerce` seed 文档集合。
- 升级 `KnowledgeIndexService` 的切分粒度，减少“多条规则混一块”。
- 调整 `TaskPipelineService` 的检索 query 组装，降低标签词噪音。
- 让 `RetrievalProfileProvider` 的 `keywords / synonyms / constraints` 真正进入召回。
- 让默认 seed 支持重建，不再长期保留旧粗块索引。

**分工**
- 主控：总控、集成、阶段验收、浏览器联调、最终结论。
- Agent A：事实型知识资料补充与知识卡整理。
- Agent B：知识库切分与默认 seed 重建。
- Agent C：检索 query、召回增强与可解释性。

**阶段完成标准**
- 默认知识库不再只有 4 篇泛规则文档。
- 检索对不同商品输入不再总是固定命中同一组模板文档。
- 切分后的 chunk 更细，默认 seed 可自动重建。
- API 相关测试通过，且至少完成一轮真实商品手测。

## Part 2: 证据与统一测试

**目标**
- 让项目具备“可证明”的 AI 应用开发证据，而不是只有能跑通的页面。
- 让面试、答辩、验收可直接看到真实 provider、召回、失败分支和系统稳定性表现。

**范围**
- 并发、重复提交、卡死、弱检索、幻觉对抗、坏样本评测。
- provider / top-k / selected hits / 导出状态 / 失败原因的诊断展示。
- 失败矩阵、评测集、统一联测与测试报告。

**分工**
- 主控：统一验收、风险汇总、最终联测。
- Agent D：系统级测试与坏样本评测。
- Agent E：后台/诊断页证据展示。

**阶段完成标准**
- 有一套可复现的系统级测试证据。
- 有一套任务级诊断信息可看。
- 有一份统一联测结论，明确“可上线演示 / 不可上线”的边界。

## 执行顺序

1. 先完成 Part 1，不夹带 Part 2 的展示性工作。
2. Part 1 完成后做阶段测试，确认主链、检索、切分、seed 重建都成立。
3. 再进入 Part 2，集中补证据、评测和系统级测试。
4. 最后做一次统一联测，输出最终清单。

## Part 1 阶段结果（2026-07-05）

- 已补齐默认 `ecommerce` 知识底座，除了原有 4 篇规则/模板文档，还新增了 5 张事实型知识卡：
  - 黑咖啡浓缩液
  - 便携挂脖小风扇
  - 洁面个护清洁
  - 轻食零食
  - 宠物清洁
- 默认 seed 现在不再只看 `indexed + chunk_count > 0`。
  - 系统会用当前源文件重新计算期望 chunk 与 retrieval_text，并和库存做比对。
  - 源文档变化、chunk 粒度变化、retrieval profile 变化，都会触发自动重建。
- chunk 切分已经收细：
  - 列表规则按更原子的单条块切分
  - 长段落会继续按句子和长度拆开
  - 检索结果最终按文档去重，不再让同一份资料的多个 chunk 抢满前排
- retrieval query 与召回增强已经接上：
  - `product_request` 改成“短标签 + 强信号”格式
  - `keywords / synonyms / constraints` 已真正进入 query 画像与排序
  - 中文电商场景会额外强化 `小红书 / 种草 / 详情页 / 真实体验 / 使用感 / 场景感` 这类信号
- 阶段验证结果：
  - 第一部分相关单测与回归：`33 passed`
  - 正式 API 校验：`powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api` 通过
- 阶段手测（测试夹具 fake provider 下的稳定回归）已观察到命中分化：
    - 黑咖啡浓缩液：命中 `黑咖啡浓缩液事实卡 + 平台文案差异 + 商品资料模板`
    - 便携挂脖小风扇：命中 `便携挂脖小风扇事实卡 + 商品资料模板 + 平台文案差异`
    - 弱输入洁面乳：命中 `洁面个护清洁事实卡 + 商品资料模板 + 平台文案差异`，且保留弱输入风险提示
- 当前遗留但不阻塞 Part 2 的点：
- 真实模型链路的超时、失败和重试证据需要在第二部分补成可诊断项，但不再允许用 deterministic fallback 代替正式结果。
