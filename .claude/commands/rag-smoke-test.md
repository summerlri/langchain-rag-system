---
description: 对真实知识库执行三条问答和一条多轮追问冒烟测试
allowed-tools: Bash(python:*) Bash(py:*)
---

确认用户接受真实百炼调用可能产生少量费用，然后运行：

```bash
python scripts/rag_ops.py smoke
```

脚本使用 JSON 登录，创建临时测试会话，解析 SSE，并验证来源、答案关键词、多轮改写和完成事件。报告每项耗时与通过状态；不要把真实 token 或完整认证信息输出到日志。
