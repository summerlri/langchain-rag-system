---
description: 根据 unit、api、rag、coverage 或 all 范围运行项目自动化测试
allowed-tools: Bash(python:*) Bash(py:*)
---

参数默认为 `all`：

```bash
python -m pytest tests/ -v
```

其他范围：

```bash
python -m pytest tests/unit/ -v
python -m pytest tests/api/ -v
python -m pytest tests/rag/ -v
python -m pytest tests/ -v --cov=backend --cov-report=term-missing
```

优先使用项目现有虚拟环境，不在每次测试前重复安装依赖。报告通过、失败、跳过、覆盖率和关键未覆盖路径；失败时只诊断，除非用户同时要求修复。
