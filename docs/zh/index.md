<p align="center">
  <img src="../images/logo.svg" alt="CoAuthors Logo" width="56" style="vertical-align:middle;" />
  <span style="font-size:1.8rem;font-weight:700;vertical-align:middle;margin-left:8px;">CoAuthors 文档</span>
</p>

CoAuthors 是 DBLP 合作者关系查询前端，重点负责页面交互、查询编排和运行时观测能力。

## CoAuthors 的职责

- 渲染合作者查询页面与结果视图
- 对输入作者进行清洗、标准化与请求组装
- 读写本地运行时缓存并记录查询遥测事件
- 对接后端 `DblpService` 完成数据查询

## 运行时特性

- 服务入口：`GET /`
- 本地运行时接口：
  - `GET /api/runtime/stats`
  - `POST /api/runtime/cache/get`
  - `POST /api/runtime/cache/put`
  - `POST /api/runtime/query/event`
- 运行时存储：SQLite（`runtime.sqlite`）
- 缓存行为：基于请求 payload 键值持久化到 `query_cache`

## 集成拓扑

- 前端入口：`http://localhost:8090`
- 后端目标：通过 `API_BASE_URL` 指向（默认 `http://localhost:8091`）
- DBLP 建库和查询生命周期由 `DblpService` 提供

## 推荐阅读路径

1. [快速开始](quickstart.md)
2. [配置说明](configuration.md)
3. [接口说明](api.md)
4. [开发文档](develop.md)
5. [运维手册](operations.md)
6. [故障排查](troubleshooting.md)
7. [变更记录](changelog.md)

## 适用读者

- 独立部署 CoAuthors 前端的工程师
- 需要将前端流程接入 DBLP 后端服务的团队
- 关注缓存命中、遥测与稳定性的维护者


