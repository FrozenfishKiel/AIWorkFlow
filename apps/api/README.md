# API App

这里是当前项目的后端主业务层，正式服务于 `电商商品内容生产系统`。

## 当前正式职责

后端当前负责跑通这条链：

1. 接收商品基础信息和任务描述
2. 生成商品理解结果
3. 匹配固定电商业务资料
4. 生成三类内容初稿
5. 返回风险提醒与参考依据
6. 提供结果导出

## 当前主入口

- `GET /auth/config`
- `POST /auth/login`
- `GET /auth/me`
- `POST /product-content/jobs`
- `GET /product-content/jobs/{task_id}`
- `POST /exports`
- `GET /exports`
- `GET /exports/{export_job_id}`
- `GET /exports/{export_job_id}/artifact`
- `GET /health`

说明：

- `product-content` 是当前前端正式消费的生成入口
- 导出仍复用统一导出链
- 知识资料默认由系统启动时自动种子写入，不要求用户先手动登记

## 当前实现现实

- 主链底层仍是异步执行：
  - 创建任务后交给 Celery
  - 前端只围绕“当前这一轮生成结果”轮询
- 本地默认 SQLite 环境下，如果 Redis / Celery 暂时不可用：
  - `POST /product-content/jobs` 会自动回退为进程内同步执行
  - `POST /exports` 也会在当前 API 进程内直接完成导出
  - 这样本地联调不再强依赖 Docker 和独立 Worker
- 生成 provider 当前支持：
  - `deepseek`
  - `auto`
- 当前本地默认建议使用 `auto`
- 当环境里存在 `DEEPSEEK_API_KEY` 时，`auto` 会优先走 DeepSeek 真链
- 当前正式链路不再保留 deterministic 保底生成分支；如果 DeepSeek 配置缺失或响应异常，任务应直接失败并暴露错误
- 默认会自动补入最小电商资料包，保证主链可直接演示
- 导出当前支持：
  - `markdown`
  - `structured_text`
- 最小登录边界已经可用：
  - legacy Bearer
  - 单操作者密码登录

## Python 规则

项目 Python 一律使用：

```powershell
D:\Anaconda3\envs\ai-content-ops\python.exe
```

不要使用系统 `python`、系统 `pip` 或 base 环境。

## 运行目录

- 运行目录：`.runtime/`
- 默认数据库：`.runtime/data/app.db`
- 默认导出目录：`.runtime/exports`
- 默认上传目录：`.runtime/uploads`

## 模型相关环境变量

- `TASK_GENERATION_PROVIDER`
- `RETRIEVAL_PROFILE_PROVIDER`
- `RETRIEVAL_EMBEDDING_DIMENSION`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_API_BASE_URL`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_TIMEOUT_SECONDS`

当前自动化测试通过测试夹具里的 fake provider 隔离外部 API；日常本地联调与正式演示默认都应保持真实 DeepSeek 链路。

## 鉴权相关环境变量

- `API_ACCESS_TOKEN`
- `AUTH_LOGIN_USERNAME`
- `AUTH_LOGIN_PASSWORD`
- `AUTH_SECRET_KEY`
- `AUTH_TOKEN_TTL_MINUTES`
- `AUTH_TOKEN_ISSUER`

## 安装依赖

```powershell
cd apps/api
D:\Anaconda3\envs\ai-content-ops\python.exe -m pip install -r requirements-dev.txt
```

## 校验

```powershell
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api
```
