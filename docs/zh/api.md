# 接口说明

## 前端服务接口

### `GET /`

返回 CoAuthors 查询页面。

### `GET /api/runtime/stats`

返回运行时统计信息。

### `POST /api/runtime/cache/get`

请求体：

```json
{ "key": "pairs:v1:abcd1234" }
```

### `POST /api/runtime/cache/put`

请求体：

```json
{ "key": "pairs:v1:abcd1234", "data": { "left_authors": [], "right_authors": [] } }
```

### `POST /api/runtime/query/event`

用于记录查询命中、耗时、错误信息。

## 依赖的 DblpService 接口

- `GET /api/health`
- `GET /api/stats`
- `GET /api/pc-members`
- `POST /api/coauthors/pairs`
