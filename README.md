# AI 内容生产与运营工作流系统

这是一个面向单任务内容生产场景的异步工作流项目。当前仓库已经具备可运行的后端异步主链、人工审核硬门、审核后快照导出、最小知识索引与检索闭环，以及一条真实可跑的自动化校验链。

## 当前已实现

- `FastAPI + SQLModel + Celery + Redis` 异步任务主链
- 任务创建、列表、详情查询
- 人工审核启动、保存、批准、驳回、驳回后重跑
- `approved_snapshot` 审核后快照固化，导出只消费该快照
- 本地知识文档登记、切块、索引、最小词法检索
- 任务级 `knowledge_domain` 检索范围约束
- 文件任务基于真实上传文本参与理解与检索
- 理解结果已显式输出风险点、不确定项、输入质量标记
- URL 任务已显式输出抽取标题、抽取器类型与浅抽取标记，便于人工判断是源内容问题还是正文抽取问题
- 工作流结果已显式输出证据摘要、上下文摘要、手工检查项、处理轨迹
- 可选最小 Bearer 访问门禁
- 前端单页任务工作台
- 前端文本、URL、文件任务创建入口
- 前端审核区可编辑草稿、理解结果、引用命中
- 导出任务轮询与制品下载收口
- 最小 `markdown` / `structured_text` 导出落盘
- 根目录 acceptance 测试与统一校验脚本

## 当前未实现

- 真实模型驱动的内容理解与生成
- 向量检索、pgvector 实际检索链、LangGraph 实际编排
- 登录页、用户体系、细粒度权限控制
- 独立 `AuditLog` 审计实体与审计视图
- 知识索引控制台入口
- 完整导出历史与导出管理页
- 压力测试与更完整的风险测试资产

## 使用边界

当前前端工作台已经开放 `text`、`url`、`file` 三种创建方式。文件任务走的是专门的 multipart 上传接口，不和 JSON 创建接口混用。

当前检索是“真实可运行但能力很轻”的最小实现：本地文档切块后做词法重叠检索，支持任务级 `knowledge_domain` 范围过滤；文件任务会用真实上传文本参与检索，URL 任务已经能优先抽取 `article/main` 正文并暴露抽取质量信号，但还不是成熟的文章级抽取与清洗链，不要把它误认为已经完成了生产级 RAG。

当前主链已经开始正面暴露一些 AI 应用核心问题，而不是把它们全藏进黑盒里：输入质量、风险点、不确定项、证据使用、上下文装配和处理轨迹现在都已经有 reviewer-visible 字段，但这仍然不等于这些问题已经被完整解决，它只说明这条链开始具备可审查性。

当前访问控制也只是最小门禁：如果配置了 `API_ACCESS_TOKEN`，后端会对 `/health` 以外的接口要求 `Bearer` token；前端下载导出制品也通过同一 API 鉴权链发起，这不等于完整登录系统。

## 快速导航

- 项目需求与范围：[docs/01-project-specs/2026-06-29-项目需求与环境准备方案.md](/D:/Projects/ai-content-production-ops-workflow/docs/01-project-specs/2026-06-29-项目需求与环境准备方案.md)
- 正式技术方案：[docs/02-architecture/2026-06-29-项目正式技术方案.md](/D:/Projects/ai-content-production-ops-workflow/docs/02-architecture/2026-06-29-项目正式技术方案.md)
- 首轮实现审查与交接：[docs/04-development-guides/2026-06-30-首轮实现审查与交接说明.md](/D:/Projects/ai-content-production-ops-workflow/docs/04-development-guides/2026-06-30-首轮实现审查与交接说明.md)
- 冷启动与操作员验证：[docs/04-development-guides/2026-06-30-冷启动与操作员验证清单.md](/D:/Projects/ai-content-production-ops-workflow/docs/04-development-guides/2026-06-30-冷启动与操作员验证清单.md)
- 本轮代码审查与风险说明：[docs/04-development-guides/2026-06-30-代码审查与风险说明.md](/D:/Projects/ai-content-production-ops-workflow/docs/04-development-guides/2026-06-30-代码审查与风险说明.md)
- 人工终审包说明：[docs/04-development-guides/2026-07-01-人工终审包说明.md](/D:/Projects/ai-content-production-ops-workflow/docs/04-development-guides/2026-07-01-人工终审包说明.md)

## 本地启动

1. 启动基础服务：

```powershell
docker compose -f infra/docker-compose.yml up -d
```

2. 安装 API 依赖：

```powershell
cd apps/api
D:\Anaconda3\envs\ai-content-ops\python.exe -m pip install -r requirements-dev.txt
```

3. 安装 Web 依赖：

```powershell
cd apps/web
npm install
```

4. 运行统一校验：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all
```

更完整的冷启动、人工验证、风险说明请看 `docs/04-development-guides/` 下的专项文档。
