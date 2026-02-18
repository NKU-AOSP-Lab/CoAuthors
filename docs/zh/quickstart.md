# 快速开始

## 本地运行

```bash
cd CoAuthors
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8090
```

访问：`http://localhost:8090`

## 启动依赖后端

CoAuthors 需要一个可用的 `DblpService`：

```bash
cd CoAuthors/DblpService
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8091
```

## Docker 独立部署

```bash
cd CoAuthors
docker compose up -d --build
```

默认服务：

- `coauthors-frontend`: `8090`
- `coauthors-dblp-service`: `8091`
