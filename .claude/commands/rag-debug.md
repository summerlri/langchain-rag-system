---
description: 诊断后端、SQLite、ChromaDB、缓存和失败文档；默认不调用收费 API
allowed-tools: Bash(python:*) Bash(py:*)
---

在项目根目录运行：

```bash
python scripts/rag_ops.py debug
```

默认只执行本地检查。如果用户明确同意调用百炼 Embedding，再运行：

```bash
python scripts/rag_ops.py debug --check-embedding
```

按 ✅/⚠️/❌ 汇总结果，并对失败项给出下一步建议；只诊断，不修改数据或配置。
