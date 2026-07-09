# 电商商品内容生产系统

这是一个围绕 `AI 应用开发主链` 搭建的电商商品内容生产项目。  
它不做生图，不做平台化壳子，核心只做一件事：

输入商品事实和任务描述，系统先理解商品，再结合固定业务资料，生成三类可继续编辑的内容初稿。

当前正式主链输出：

- 电商卖点文案
- 商品详情页文案
- 小红书 / 种草短文案

## 1. 你拿到这个项目后，先知道三件事

1. 这个项目可以本地直接跑，不要求一开始就部署公网。
2. 真正会产生成本的是你自己配置进去的模型 Key，不是这个仓库本身。
3. 第一次运行时，如果没有配置模型参数，前端工作台里会出现“本机模型配置”卡片，你可以直接在页面里填入你自己的 DeepSeek Key，它会写入 `apps/api/.env.local`。

也就是说，别人下载你的项目以后，不会再默认使用“你的 API”；谁来配置 Key，谁承担对应模型调用费用。

## 2. 项目现在能做什么

主流程：

1. 输入商品基础信息
2. 输入这一轮任务描述
3. 系统做商品理解
4. 系统检索固定电商业务资料
5. 系统生成三类内容初稿
6. 展示风险提醒、生成依据和诊断信息
7. 导出当前结果

前端正式入口现在是：

- 官网首屏
- 工作台主页面
- 工作台内的“生成依据”
- 工作台内的“诊断后台”
- 工作台内的“本机配置”

## 3. 运行环境要求

你自己的机器需要准备：

- Python 3.11 或 3.12
- Node.js 20+
- npm 10+

如果你想跑完整异步链路，还需要：

- Docker Desktop

如果你只是先本地验证主流程，不启 Docker 也可以。  
当前 API 在 Redis / Celery 不可用时，会自动回退到进程内执行，方便本地演示和测试。

## 4. 首次安装

先克隆仓库，然后分别安装后端和前端依赖。

### 4.1 后端

在你自己的 Python 虚拟环境里执行：

```powershell
cd apps/api
<PYTHON> -m pip install -r requirements-dev.txt
```

说明：

- `<PYTHON>` 请替换成你自己机器上的 Python 可执行文件
- 维护者本机使用的是 `D:\Anaconda3\envs\ai-content-ops\python.exe`
- 你不需要和维护者使用同一条路径

### 4.2 前端

```powershell
cd apps/web
npm install
```

## 5. 配置方式

### 5.1 最推荐的方式：启动后在网页里配

项目现在提供了本机配置接口：

- `GET /runtime-config`
- `PUT /runtime-config`

首次进入工作台时，如果还没配置模型，页面会提示你填写：

- `DeepSeek API Key`
- `DeepSeek Base URL`
- `DeepSeek 模型`

保存后会写入：

```text
apps/api/.env.local
```

这份文件是本机本仓库私有配置，不应该提交到 git。

### 5.2 手动配置方式

如果你更习惯手改文件，可以先复制示例文件：

```powershell
Copy-Item apps/api/.env.example apps/api/.env.local
Copy-Item apps/web/.env.example apps/web/.env.local
```

然后至少补上后端里的：

```env
DEEPSEEK_API_KEY=你的 Key
```

如果你要改 API 地址，也可以修改前端里的：

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 6. 启动方式

### 6.1 只跑本地主流程

先启动 API：

```powershell
cd apps/api
<PYTHON> -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

再启动 Web：

```powershell
cd apps/web
npm run dev
```

打开：

- Web: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- API Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 6.2 跑完整异步链路

先启动基础依赖：

```powershell
docker compose -f infra/docker-compose.yml up -d
```

然后再分别启动 API 和 Web。

## 7. 怎么用

启动后按这个顺序体验：

1. 打开首页
2. 点击“进入工作台”
3. 如果出现“本机模型配置”，先填你自己的 DeepSeek Key
4. 如果当前环境开启了密码登录，先登录
5. 填写商品信息和任务描述
6. 提交生成
7. 在结果区看三类初稿
8. 需要时打开“生成依据”看系统理解、参考资料、卖点提炼和风险提示
9. 需要时打开“诊断后台”看链路、召回候选、审计时间线和导出状态
10. 导出结果继续编辑

## 8. 鉴权说明

当前项目支持三种状态：

- `disabled`：不启登录，直接使用
- `legacy_token`：使用固定 Bearer Token
- `password_login`：使用单操作者用户名密码登录

如果你要启用密码登录，需要在 `apps/api/.env.local` 里补齐：

```env
AUTH_LOGIN_USERNAME=operator
AUTH_LOGIN_PASSWORD=your-password
AUTH_SECRET_KEY=至少16位
```

## 9. 目录和运行产物

运行时文件默认写到：

```text
.runtime/
```

主要包括：

- `.runtime/data/app.db`
- `.runtime/logs/`
- `.runtime/uploads/`
- `.runtime/exports/`

## 10. 测试与校验

仓库统一校验入口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all
```

如果你只想分别验证：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope web
```

## 11. 常见问题

### 11.1 为什么别人下载后不会用到我的 API？

因为模型 Key 不再写死在代码里。  
现在谁在自己的机器上配置 `DEEPSEEK_API_KEY`，主链就使用谁配置的 Key。

### 11.2 不启 Docker 能不能用？

可以。  
本地主流程可以先跑，API 会在 Redis / Celery 不可用时回退到进程内执行。

### 11.3 为什么点进工作台先让我配 Key？

因为当前正式链路已经不保留 deterministic 保底分支，真实生成要走真实模型调用，所以第一次必须先配置模型。

## 12. 关键文档

- 项目需求：[docs/01-project-specs/2026-06-29-项目需求与环境准备方案.md](/D:/Projects/ai-content-production-ops-workflow/docs/01-project-specs/2026-06-29-项目需求与环境准备方案.md)
- 正式技术方案：[docs/02-architecture/2026-06-29-项目正式技术方案.md](/D:/Projects/ai-content-production-ops-workflow/docs/02-architecture/2026-06-29-项目正式技术方案.md)
- 当前实施计划：[docs/03-implementation-plans/2026-07-03-电商商品内容生产系统收口实施计划.md](/D:/Projects/ai-content-production-ops-workflow/docs/03-implementation-plans/2026-07-03-电商商品内容生产系统收口实施计划.md)
