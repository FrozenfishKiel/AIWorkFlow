# 电商商品内容生产系统

这是一个聚焦 `AI 应用开发主链` 的电商商品内容生产项目。

当前正式用户流程已经收口为：

- 用户输入 `商品基础信息 + 一句任务描述`
- 系统先做商品理解
- 系统结合内置电商业务资料做参考召回
- 系统输出 `供运营二次编辑的高质量初稿`

当前一次会同时产出三类结果：

- `电商卖点文案`
- `商品详情页文案`
- `小红书 / 种草短文案`

## 当前主链

这版项目不再把“任务列表工作台”当成产品中心，而是强调一条更完整的 AI 应用链路：

1. 商品信息输入
2. 商品任务理解
3. 固定业务资料匹配
4. 卖点提炼
5. 多类型内容生成
6. 风险与口径提醒
7. 结果导出

内置的最小业务资料包当前包括：

- 品牌语气规范
- 平台文案差异
- 历史优稿参考

## 当前已落地

- `FastAPI + SQLModel + Celery + Redis` 后端异步执行链
- 本地 SQLite 环境下，若 Redis / Celery 不可用，商品生成与导出会自动回退为进程内同步执行
- `POST /product-content/jobs` 与 `GET /product-content/jobs/{task_id}` 商品内容生成接口
- DeepSeek 真链生成分支
- 本地与正式演示统一要求真实模型链路；`TASK_GENERATION_PROVIDER` / `RETRIEVAL_PROFILE_PROVIDER` 当前只支持 `deepseek` 口径，`auto` 仅表示按本机已配置的 DeepSeek 参数自动接通
- 固定电商知识资料自动种子写入
- 结果导出能力
- 最小登录边界：
  - legacy Bearer
  - 单操作者账号密码登录
- 中文前端工作区：
  - 商品信息输入
  - 自动轮询当前结果
  - 三类初稿展示
  - 生成依据抽屉：
    - 系统理解
    - 参考资料
    - 卖点提炼
    - 风险提示
  - 弱输入提醒与结果风险提示
  - 当前结果导出
- API / Web 自动化校验脚本

## 当前边界

- 当前输出是 `高质量初稿`，不是最终发布稿
- 外部网页资料抓取不属于当前正式产品链
- AI 自动上网搜集业务资料可单独作为资料准备方案，不进入当前主产品
- 前端不再以任务列表、知识索引、导出历史为主视图

## 快速开始

1. 启动基础依赖（需要完整异步链时）

```powershell
docker compose -f infra/docker-compose.yml up -d
```

如果只是本地先跑通商品内容主流程，当前也可以不启动 Docker，API 会在本地 SQLite 环境下自动回退为同步执行。

2. 安装 API 依赖

```powershell
cd apps/api
D:\Anaconda3\envs\ai-content-ops\python.exe -m pip install -r requirements-dev.txt
```

3. 安装 Web 依赖

```powershell
cd apps/web
npm install
```

4. 运行校验

```powershell
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all
```

## 关键文档

- 项目需求：[docs/01-project-specs/2026-06-29-项目需求与环境准备方案.md](/D:/Projects/ai-content-production-ops-workflow/docs/01-project-specs/2026-06-29-项目需求与环境准备方案.md)
- 正式技术方案：[docs/02-architecture/2026-06-29-项目正式技术方案.md](/D:/Projects/ai-content-production-ops-workflow/docs/02-architecture/2026-06-29-项目正式技术方案.md)
- 当前收口实施计划：[docs/03-implementation-plans/2026-07-03-电商商品内容生产系统收口实施计划.md](/D:/Projects/ai-content-production-ops-workflow/docs/03-implementation-plans/2026-07-03-电商商品内容生产系统收口实施计划.md)
