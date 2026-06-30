# API App

## 现在这层后端负责什么

这里放的是当前项目的后端主业务代码。它已经承担真实的任务创建、异步处理、审核状态机、知识索引、检索、导出落盘这些核心责任，但还没有进入“完整生产级平台”状态。

当前已经落地的关键能力：

- `POST /tasks`
- `POST /tasks/upload`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `POST /reviews/{task_id}/start`
- `PUT /reviews/{task_id}`
- `POST /reviews/{task_id}/approve`
- `POST /reviews/{task_id}/reject`
- `POST /reviews/{task_id}/rerun`
- `POST /exports`
- `GET /exports/{export_job_id}`
- `GET /exports/{export_job_id}/artifact`
- `POST /knowledge/index-local`
- `GET /knowledge/documents/{document_id}`
- `GET /health`

## 当前实现现实

- 任务主链是真异步，创建任务后会把慢操作交给 Celery。
- 审核门是真门，导出只认 `approved_snapshot`。
- 知识检索是真链路，但目前是最小词法检索，不是生产级向量 RAG。
- 任务现在可以携带可选 `knowledge_domain`，检索会按这个范围收口，而不是默认全库乱找。
- 文件任务在 pipeline 中会直接读取上传后的本地文本参与理解和检索；URL 任务已经会抓取公开 HTML 并做基础正文抽取，但还不是成熟的文章级抽取与清洗链。
- 文件上传接口已经接通前端入口，但仍受扩展名、大小和安全边界限制。
- 导出制品现在通过 API 下载路由交付，不要求前端读取服务器裸文件路径。
- 上传文件、导出文件当前都落在仓库内统一的 `.runtime/` 目录，不是 MinIO 应用链路。
- 已支持最小 Bearer 访问门禁，但还没有登录、用户体系、权限模型。

## 最小访问门禁

如果配置下面任一环境变量：

- `API_ACCESS_TOKEN`
- `AI_CONTENT_OPS_API_ACCESS_TOKEN`

那么除了 `/health` 以外的 API 都必须带：

```text
Authorization: Bearer <your-token>
```

如果不配置，上述门禁默认关闭，保留当前本地开发体验。

## Python 规则

项目 Python 一律使用：

```powershell
D:\Anaconda3\envs\ai-content-ops\python.exe
```

不要用系统 `python`、系统 `pip`、`base`、`py -3.12`。

## 运行目录

- 默认运行目录统一收口到仓库根目录下的 `.runtime/`
- 默认 SQLite 路径：`.runtime/data/app.db`
- 默认导出目录：`.runtime/exports`
- 默认上传目录：`.runtime/uploads`

如果要覆盖运行目录，使用：

- `APP_RUNTIME_DIR`

## 安装依赖

```powershell
cd apps/api
D:\Anaconda3\envs\ai-content-ops\python.exe -m pip install -r requirements-dev.txt
```

## 校验

```powershell
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api
```

这会检查：

- compose 配置
- API compile/import
- API pytest
- 根目录 acceptance pytest

## 现在别误会的几件事

- `pgvector` 镜像在 compose 里有，不代表当前检索已经走向量链。
- `MinIO` 服务在 compose 里有，不代表当前上传/导出已经走对象存储。
- `LangGraph` 在技术方案里是目标能力，不代表当前代码里已经正式接上。
- 最小 Bearer 门禁已经有了，但这不等于完整认证和权限系统。
