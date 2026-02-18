<div align="center" style="display:flex;justify-content:center;align-items:center;gap:8px;">
  <img src="./static/coauthors-logo.svg" alt="CoAuthors Logo" width="34" />
  <strong>CoAuthors</strong>
</div>

<p align="center">DBLP 合作者关系查询前端，提供缓存与运行观测能力。</p>

<p align="center">[<a href="./README.md"><strong>EN</strong></a>] | [<a href="./README.zh-CN.md"><strong>CN</strong></a>]</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-1f7a8c" alt="version" />
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi&logoColor=white" alt="fastapi" />
  <img src="https://img.shields.io/badge/docs-MkDocs-526CFE?logo=materialformkdocs&logoColor=white" alt="docs" />
</p>

## 项目概览

CoAuthors 是 DBLP 合作者查询的 Web 前端项目，聚焦页面交互、结果矩阵渲染与运行时可观测性；DBLP 数据构建与查询能力由 `DblpService` 提供。

## 核心能力

- 发起合作者查询并展示协作矩阵结果。
- 调用后端接口获取作者对协作统计数据。
- 使用 SQLite 持久化运行时缓存与遥测事件。
- 暴露运行时统计接口，便于前端调试和验收。

## 本地运行

```bash
cd CoAuthors
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8090
```

可选地同时启动内置后端（推荐本地联调时使用）：

```bash
cd CoAuthors/DblpService
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8091
```

访问地址：

- `http://localhost:8090/`
- `http://localhost:8091/bootstrap`

## Docker 启动

```bash
cd CoAuthors
docker compose up -d --build
```

默认端口：

- `coauthors-frontend`: `8090`
- `coauthors-dblp-service`: `8091`

## 文档

- 英文文档：`docs/en/`
- 中文文档：`docs/zh/`

本地预览：

```bash
cd CoAuthors
python -m pip install -r docs/requirements.txt
mkdocs serve
```


