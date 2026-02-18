# 开发文档

## 1. 架构与边界

CoAuthors 是查询前端，不承担 DBLP 建库与学术数据计算，职责拆分如下：

1. **HTTP/UI 层**（`app.py`、`templates/`、`static/`）
   - 渲染页面 `GET /`。
   - 提供本地 runtime API（缓存与遥测）。
2. **Runtime 持久化层**（`runtime_store.py`）
   - 通过 SQLite 保存访问、缓存、查询事件与日志。
3. **后端集成层**（`static/query_app.js` + `API_BASE_URL`）
   - 将共作请求转发给 DblpService 的 `POST /api/coauthors/pairs`。

真实的作者解析、共作计算、数据库约束由 `CoAuthors/DblpService` 负责。

## 2. 端到端请求链路

### 2.1 页面访问链路

1. 浏览器请求 `GET /`。
2. `app.py` 调用 `RuntimeStore.record_page_visit()`，写 `page_visits` + 计数器 `visit_count`。
3. 返回 `index.html`，注入：
   - `app_version`
   - `visit_count`
   - `api_base`（来自 `API_BASE_URL`）

### 2.2 共作查询链路（含缓存）

1. 前端读取左右作者输入，按行拆分（`parseLines`）。
2. 对每条作者做清洗（`sanitizeAuthorEntries`）：
   - 去首尾空格，压缩中间空白。
   - 截断组织后缀（如 `Name || Org`、`Name (Org)` 等）。
   - 去重，保留首次出现顺序。
3. 构造查询 payload（`left/right/exact_base_match/limit_per_pair/author_limit/year_min`）。
4. 生成缓存键：`pairs:v1:<fnv1a32(json_payload)>`。
5. 调用本地缓存读取 `POST /api/runtime/cache/get`。
6. 命中时直接渲染；未命中时调用 DblpService `POST /api/coauthors/pairs`。
7. 远端成功结果异步写入本地缓存 `POST /api/runtime/cache/put`。
8. 上报遥测 `POST /api/runtime/query/event`（成功或失败都会记录）。

注意：缓存写入与遥测上报是“尽力而为”（失败被吞掉，不阻断主查询流程）。

## 3. 缓存设计（重点）

### 3.1 缓存分层

- **L1（前端内存态）**：本次页面生命周期内的渲染状态（如 pair selector 当前项）。
- **L2（SQLite 持久化）**：`query_cache` 表，跨请求、跨刷新生效。

### 3.2 L2 键与值

- 键：`cache_key`，当前命名空间为 `pairs:v1:*`。
- 值：完整响应 JSON（`response_json`）。
- 命中元数据：`hit_count`、`last_hit_at`。

### 3.3 失效策略

- 当前**没有 TTL**、**没有 LRU**、**没有容量上限**。
- 新请求同 key 会覆盖旧值（`ON CONFLICT DO UPDATE`）。
- 若底层 DBLP 数据更新，旧 cache 不会自动失效，需要手工清理或换 key 版本（如 `pairs:v2`）。

## 4. 并发模型与超限行为（等待 / 拒绝 / 降级）

| 场景 | 约束 | 超限行为 | 结果 |
|---|---|---|---|
| 前端作者数量 | 每侧最多 `50` | 前端直接拦截（不发请求） | UI 错误提示 |
| DblpService 作者数量 | 每侧最多 `MAX_ENTRIES_PER_SIDE`（默认 50，硬上限 50） | 立即拒绝 | `400` |
| `limit_per_pair` | 夹紧到 `[1, MAX_LIMIT]`（默认 MAX_LIMIT=200） | 不拒绝，自动夹紧 | `200` 正常返回 |
| `author_limit` | 最大 `MAX_AUTHOR_RESOLVE`（默认 800） | 不拒绝，自动夹紧 | `200` 正常返回 |
| Runtime SQLite 写冲突 | `sqlite timeout=30s` + `WAL` | 先等待锁 | 超时后抛异常（通常表现为 `500`） |
| DblpService DB 锁冲突 | `PRAGMA busy_timeout=30000` | 先等待锁 | 超时后失败（常见 `500`，连接不可用时 `503`） |
| Pipeline 重复启动 | 仅允许一个 pipeline 线程 | 立即拒绝 | `409 Pipeline is already running` |
| Pipeline 运行中 reset | 不允许 reset | 立即拒绝 | `409 Cannot reset while running` |
| Runtime 缓存读取失败 | 无 | 查询降级到后端直连 | 业务继续 |
| Runtime 缓存写入/遥测失败 | 无 | 忽略失败 | 业务继续 |

结论：本系统对“流量并发”主要是**等待数据库锁**；对“违反业务上限”是**立即拒绝**；对“观测与缓存故障”是**降级不中断**。

## 5. API 输入约束与错误语义

### 5.1 CoAuthors runtime API（`app.py`）

- `POST /api/runtime/cache/get`
  - `key`: `1..256` 字符。
  - 不合法请求由 FastAPI/Pydantic 返回 `422`。
- `POST /api/runtime/cache/put`
  - `key`: `1..256`。
  - `data`: JSON object。
  - `key` 去空白后为空会返回 `400`。
- `POST /api/runtime/query/event`
  - `left_count/right_count`: `0..500`
  - `total_pairs`: `0..250000`
  - `duration_ms`: `0..86400000`
  - `error_message`: 最长 `1000`
  - 越界同样返回 `422`。

### 5.2 DblpService 查询 API

- `POST /api/coauthors/pairs` 要求左右作者都非空，否则 `400`。
- 数据库文件不存在或 schema 不完整时返回 `503`。

## 6. Runtime 表结构与观测指标

`runtime_store.py` 初始化下列表：

- `runtime_counters`
- `page_visits`
- `query_cache`
- `query_events`
- `event_logs`

核心指标建议：

- 查询总量：`query_event_count`
- 缓存命中：`cache_hit_count`
- 缓存写入：`cache_write_count`
- 缓存规模：`query_cache` 行数
- 错误占比：`query_events.success=0` 比例

## 7. 开发与扩展建议

- 业务计算逻辑保持在 DblpService，CoAuthors 仅做编排与展示。
- 新增缓存键时必须升级版本前缀（如 `pairs:v2`），避免旧值污染。
- 任何新字段优先追加到 `query_events.extra_json`，减少 schema 变更。
- 增加高开销查询前，先明确行为策略是“等待、拒绝、还是降级”，并写入文档。