# 配置说明

## 核心环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `API_BASE_URL` | `http://localhost:8091` | 前端请求的 DBLP API 基地址 |
| `COAUTHORS_DATA_DIR` | `${PROJECT_DIR}/data` | 运行时目录（缓存/统计数据库） |
| `COAUTHORS_RUNTIME_DB` | `${COAUTHORS_DATA_DIR}/runtime.sqlite` | 运行时 SQLite 文件路径 |

## 运行时数据

运行时数据库包含：

- `page_visits`: 页面访问记录
- `query_cache`: 查询结果缓存
- `query_events`: 查询行为与耗时
- `event_logs`: 运行日志

## 配置建议

- 生产环境固定 `API_BASE_URL` 指向稳定域名
- 使用持久化卷保存 `runtime.sqlite`
- 前端和 DblpService 端口统一在反向代理层管理
