# 运维手册

## 部署模式

1. 独立部署：CoAuthors + 同仓 `DblpService`
2. 共享后端：多个前端指向同一个 DblpService

## 升级流程

1. 先升级 DblpService 并确认 `/api/health`
2. 再升级 CoAuthors 前端
3. 检查首页查询、缓存写入、统计上报

## 备份建议

- 定期备份 `runtime.sqlite`
- 运行时数据仅用于缓存与统计，不建议作为业务主数据

## 监控建议

- 前端可用性（`GET /`）
- 后端连通性（`GET /api/health`）
- 查询失败率（`query_events` 中 `success=0`）
