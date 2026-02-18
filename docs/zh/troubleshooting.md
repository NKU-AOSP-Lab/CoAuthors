# 故障排查

## 页面可访问，但查询失败

- 检查 `API_BASE_URL` 是否可从浏览器访问
- 检查 DblpService 是否返回 `/api/health = ok`
- 检查浏览器控制台是否有 CORS 错误

## 查询结果长期为空

- 确认 DblpService 已完成建库
- 确认请求作者名格式正确（每行一个）

## 运行时数据库异常

- 检查 `COAUTHORS_RUNTIME_DB` 路径权限
- 检查磁盘空间
- 必要时备份后重建 runtime 数据库
