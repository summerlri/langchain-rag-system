---
description: RAG 调试面板 - 检查 ChromaDB/SQLite/Embedding/缓存等所有组件状态
allowed-tools: Bash(curl:*), Bash(cd:*), Bash(python:*), Bash(ls:*), Bash(echo:*)
---

检查 RAG 系统所有组件的运行状态，快速定位问题环节。

## 诊断维度

### 1. 后端服务健康
```bash
curl -s http://localhost:8000/api/health
```
报告 FastAPI、SQLite、ChromaDB、百炼 API Key 各项状态。

### 2. 向量数据库 ChromaDB
用 Python 脚本列出所有 collection 和 chunk 数量：
```bash
cd e:/claude_daima/langchainRAG项目 && python -c "
import chromadb
from backend.config import get_settings
settings = get_settings()
client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
cols = client.list_collections()
if not cols:
    print('⚠️ 没有 collection（尚未入库任何文档）')
else:
    total = 0
    for col in cols:
        c = col.count()
        total += c
        print(f'  {col.name}: {c} chunks')
    print(f'  总计: {total} chunks')
"
```

### 3. 关系数据库 SQLite
```bash
cd e:/claude_daima/langchainRAG项目 && python -c "
import sqlite3
conn = sqlite3.connect('data/rag.db')
for t, l in [('users','用户'),('knowledge_bases','知识库'),('documents','文档'),('conversations','会话'),('messages','消息')]:
    conn.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'  {l}: {conn.fetchone()[0]} 条')
conn.execute('SELECT status, COUNT(*) FROM documents GROUP BY status')
print(f'  文档状态: {dict(conn.fetchall())}')
conn.execute(\"SELECT filename, error_message FROM documents WHERE status='failed' LIMIT 5\")
failed = conn.fetchall()
if failed:
    print(f'  ❌ 失败文档:')
    for f in failed:
        print(f'    {f[0]}: {f[1][:100] if f[1] else \"无错误信息\"}')
conn.close()
"
```

### 4. 缓存状态
```bash
ls -la e:/claude_daima/langchainRAG项目/data/cache/
```

### 5. Embedding 连通性
```bash
cd e:/claude_daima/langchainRAG项目 && python -c "
from backend.rag.embedding import BailianEmbeddings
try:
    emb = BailianEmbeddings()
    r = emb.embed_query('测试')
    print(f'✅ Embedding 正常, 维度: {len(r)}')
except Exception as e:
    print(f'❌ Embedding 失败: {e}')
"
```

### 6. 诊断总结
用表格汇总所有检查项（✅/⚠️/❌），有问题的给出修复建议。如：
- ChromaDB 为空 → 使用 `/rag-ingest` 入库
- API Key 缺失 → 检查 `.env` 中的 `DASHSCOPE_API_KEY`
- 文档入库失败 → 检查 `error_message` 字段
