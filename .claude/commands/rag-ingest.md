---
description: 上传指定文档并轮询真实入库状态
allowed-tools: Bash(python:*) Bash(py:*) Bash(ls:*)
---

从用户消息提取文件路径；缺少路径时先询问。然后运行：

```bash
python scripts/rag_ops.py ingest "<文件路径>"
```

可通过 `--kb-id <id>` 指定知识库，否则使用第一个知识库；不存在知识库时脚本会创建“默认知识库”。账号从 `RAG_ADMIN_USERNAME` 和 `RAG_ADMIN_PASSWORD` 环境变量读取，未设置时仅用于本地演示的默认值为 `admin/123456`。

报告文件名、知识库、状态、chunk 数量和耗时。失败时显示服务返回的原因，不修改源文件。
