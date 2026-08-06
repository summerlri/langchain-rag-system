---
description: 快速入库文档 - 上传指定文件到知识库并等待入库完成
allowed-tools: Bash(curl:*), Bash(cd:*), Bash(echo:*)
---

接收用户指定的文件路径，通过 API 上传文档到知识库并等待入库完成。

## 参数

用户通过 `/rag-ingest <文件路径>` 调用，你需要从用户消息中提取文件路径。

如果用户没有提供文件路径（只输入了 `/rag-ingest`），询问用户要上传哪个文件。可以提示 `data/seed_docs/` 目录中有可用的种子文档。

## 执行步骤

### 1. 验证文件存在
检查用户提供的文件路径是否存在。如果不存在，列出 `data/seed_docs/` 中的可用文件供用户选择。

### 2. 健康检查
```bash
curl -s http://localhost:8000/api/health
```
如果不可达，提示用户先启动后端。

### 3. 登录
```bash
curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=123456"
```
从 JSON 提取 `access_token`。

### 4. 获取或创建知识库
```bash
curl -s http://localhost:8000/api/knowledge-bases -H "Authorization: Bearer <token>"
```
- 如果返回空数组，创建一个默认知识库：
  ```bash
  curl -s -X POST http://localhost:8000/api/knowledge-bases -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"name": "默认知识库", "description": "自动创建的知识库"}'
  ```
  从响应提取 `id`。
- 如果有知识库，取第一个的 `id`。

### 5. 上传文档
```bash
curl -s -X POST "http://localhost:8000/api/knowledge-bases/<kb_id>/documents" -H "Authorization: Bearer <token>" -F "file=@<文件路径>"
```
从响应提取 `id`（doc_id）和 `filename`。记录开始时间。

如果返回错误（不支持的文件类型、文件过大等），报告并停止。

### 6. 轮询入库状态
每 2 秒检查文档状态，最长等待 120 秒：
```bash
curl -s "http://localhost:8000/api/knowledge-bases/<kb_id>/documents" -H "Authorization: Bearer <token>"
```
在文档列表中找 `id` 匹配的文档：
- `"processing"` → 继续轮询
- `"completed"` → 成功，提取 `chunk_count`
- `"failed"` → 失败，提取 `error_message`

### 7. 报告结果
显示：文件名 → 知识库 → chunk 数量 → 耗时（秒）→ 状态。

如果失败，显示错误原因并建议检查后端日志。
