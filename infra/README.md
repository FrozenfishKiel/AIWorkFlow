# Infra

## 作用

这里放本地开发和单机部署要用的基础服务编排文件。

当前服务组合：

- PostgreSQL
- Redis
- MinIO
- FastAPI API
- Celery worker

## 当前真实状态

- 本地开发 compose 可用，统一把运行时产物收口到仓库内 `.runtime/`
- `docker compose ... config` 校验已经纳入统一验证脚本
- 生产 override 目前还不能宣称“已经完全收口端口暴露”

这点要特别说清楚：

截至 `2026-06-30`，`docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config` 的合并结果里，API / PostgreSQL / Redis / MinIO 端口仍然会出现在配置输出中。因此现在的 `docker-compose.prod.yml` 只能算“生产意图配置”，不能算“已验证完成的生产收口配置”。

## 本地启动

```powershell
docker compose -f infra/docker-compose.yml up -d
```

## 本地校验

```powershell
docker compose -f infra/docker-compose.yml config
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config
```

## 当前不要误解的点

- compose 里有 MinIO，不代表应用代码已经把上传和导出切到 MinIO。
- compose 里有 pgvector，不代表当前检索已经是向量检索。
- override 文件存在，不代表正式部署安全收口已经全部做完。
