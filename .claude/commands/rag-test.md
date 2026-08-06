---
description: RAG 冒烟测试 - 执行 3 条问答验证检索+生成全链路是否正常
allowed-tools: Bash(curl:*), Bash(cd:*), Bash(echo:*)
---

执行 RAG 知识库问答系统的完整冒烟测试，验证整套系统是否工作正常。

## 测试用例

| 序号 | 问题 | 预期 |
|------|------|------|
| 1 | "iPhone 15 Pro Max 的售价是多少？" | 检索到相关 chunk，回答包含 ¥9,999 等价格信息 |
| 2 | "华为 Mate 60 Pro 有什么特色功能？" | 检索到相关 chunk，回答包含卫星通话、HarmonyOS |
| 3 | "如何退货？" | 检索到退换货政策相关 chunk |

## 执行步骤

### 1. 健康检查
```bash
curl -s http://localhost:8000/api/health
```
如果请求失败，提示用户先启动后端服务。

### 2. 登录
```bash
curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=123456"
```
从 JSON 响应中提取 `access_token`。

### 3. 检查知识库
```bash
curl -s http://localhost:8000/api/knowledge-bases -H "Authorization: Bearer <token>"
```
至少有一个知识库且 `doc_count > 0`。如果 doc_count 为 0，提示用户先用 `/rag-ingest` 入库文档，或运行 `python scripts/seed_data.py` 生成种子文档。

取第一个知识库的 `id` 作为 kb_id。

### 4. 创建测试会话
```bash
curl -s -X POST http://localhost:8000/api/conversations -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"kb_id": "<kb_id>", "title": "RAG冒烟测试"}'
```
提取 `id` 作为 conv_id。

### 5. 依次发送 3 个测试问题
对每个问题，用 curl SSE 流式请求：
```bash
curl -s --no-buffer -X POST "http://localhost:8000/api/chat/<conv_id>" -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"message": "<问题>", "kb_id": "<kb_id>"}'
```

SSE 格式为 `data: {...}\n\n`，解析每行 JSON：
- `"type": "sources"` → 提取 `data` 数组，记录 chunk 数量和内容
- `"type": "token"` → 拼接 `content` 为完整回答
- `"type": "done"` → 提取 `total_tokens` 和 `latency_ms`

### 6. 评估并总结
对每个测试问题报告：检索是否命中（✅/❌）、回答是否包含预期信息（✅/❌）、耗时和 token 用量。

最后用表格汇总通过率，如 "3/3 全部通过 ✅"。

有失败项时给出诊断建议（如检查 embedding API、ChromaDB 数据等）。
