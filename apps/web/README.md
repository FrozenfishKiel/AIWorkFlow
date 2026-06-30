# Web App

## 这层前端现在是什么

这是当前项目的单页任务工作台，不是平台首页，也不是多模块后台。

当前已经接通的前端能力：

- 文本任务创建
- URL 任务创建
- 文件任务创建
- 可选知识范围输入
- 任务列表
- 任务详情轮询
- 理解结果展示
- 引用命中展示
- 工作流草稿展示
- 审核启动、保存、批准、驳回、重跑
- 审核区编辑理解结果、引用命中、工作流草稿
- 已批准任务触发最小 markdown 导出
- 导出任务状态轮询
- 已完成导出制品下载

## 当前前端现实

- 轮询是当前正式机制，没有上 WebSocket。
- 文件任务通过专门的 multipart 上传接口创建，不和 JSON 创建接口混走。
- 任务表单支持可选 `knowledge domain`，用来把检索限制到一个业务范围。
- 导出体验已经补到“可发起、可轮询、可下载”，但还没有完整导出记录页和批量管理视图。
- 没有登录页，也没有用户态权限系统。
- 如果后端配置了 `API_ACCESS_TOKEN`，前端可以通过 `VITE_API_ACCESS_TOKEN` 自动带上 Bearer token。

## 启动

```powershell
cd apps/web
npm install
npm run dev
```

## 校验

```powershell
powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope web
```

## 前端边界

- 这里只消费后端结构化接口，不自己拼业务状态机。
- 审核区本地草稿不能被轮询静默覆盖，这是当前一个已经明确守住的行为边界。
- 文件创建和导出下载都必须继续沿着现有 `services / features / types / pages` 结构长，不要把 API 契约散落到组件里。
