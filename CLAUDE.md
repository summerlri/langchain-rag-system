# CLAUDE.md

本项目是基于 **LangChain + FastAPI + ChromaDB + Vue 3** 的企业级 RAG 知识库问答系统（电商场景）。

## 技术栈

- **后端**: Python FastAPI, LangChain, ChromaDB, SQLite (aiosqlite), 阿里云百炼 DashScope
- **前端**: Vue 3 + Element Plus + Vite
- **LLM**: 通义千问 qwen-plus | **Embedding**: text-embedding-v2
- **启动**: 后端 `:8000` / 前端 `:5173` | 默认账号 `admin / 123456`

## 项目结构

```
backend/api/          # REST API: auth, chat(SSE), conversation(含导出), knowledge_base
backend/rag/          # RAG 流水线: loader, splitter, embedding, vector_store, retriever, chain, pipeline
backend/models/       # SQLAlchemy ORM: User, KnowledgeBase, Document, Conversation, Message
backend/core/         # 安全/JWT, 依赖注入, 异常处理
backend/schemas/      # Pydantic 请求/响应模型
backend/cache/        # 两级缓存 (L1 内存 LRU + L2 diskcache)
backend/db/           # 数据库连接（含 busy_timeout + WAL + 连接池优化）
frontend/src/         # Vue 3 SPA
data/                 # SQLite DB + ChromaDB 向量 + 上传文件 + 种子文档
scripts/seed_data.py  # 生成电商测试知识库文档
tests/                # 单元/API/RAG 测试 + locustfile.py 压力测试
.claude/agents/       # 自定义子代理: tester, quality-engineer, gitcommit-agent 等
.claude/pass/         # 质量门禁标记文件（gitignore，不提交）
.githooks/            # Git pre-commit 钩子（拦截未经检查的提交）
```

## 自定义技能

---

### /rag-ingest — 快速入库文档

**调用**: `/rag-ingest <文件路径>` | 上传文档到知识库并等待入库完成。先检查 `GET /api/health`，用 `POST /api/auth/login`（JSON 格式 `{"username":"admin","password":"123456"}`）获取 token，再上传文件并轮询状态直到 completed/failed。

### /rag-test — RAG 冒烟测试

**调用**: `/rag-test` | 跑 3 条固定问题验证 RAG 全链路（检索+生成），汇总通过率。

### /rag-debug — RAG 调试面板

**调用**: `/rag-debug` | 检查后端健康、ChromaDB collection/chunk 数、SQLite 表统计、缓存、Embedding 连通性，输出诊断表格。

### /make-tests — 单元测试

**调用**: `/make-tests [unit|api|rag|coverage|add <文件>]` | 运行 pytest + 生成 HTML/覆盖率报告。

关键命令:
```bash
# 全部测试 + 覆盖率 + HTML 报告
pytest tests/ -v --tb=short --cov=backend --cov-report=html:reports/coverage --html=reports/test_report.html --self-contained-html
# 子集: pytest tests/unit/ -v | pytest tests/api/ -v | pytest tests/rag/ -v
```

Mock 策略: 单元测试纯逻辑 | API 用内存 SQLite | RAG 用 mock LLM/Embedding/ChromaDB。报告在 `reports/test_report.html` 和 `reports/coverage/index.html`。

### /security-audit — 安全审计

**调用**: `/security-audit [路径]` | 五大维度：硬编码敏感信息、注入漏洞、配置文件泄露、认证授权缺陷、依赖风险。只检查不修改。

### /comments-check — 注释质量

**调用**: `/comments-check [路径]` | 三维度：注释覆盖率（目标 30%）、准确性、可读性（小白视角）。跳过 tests/venv 目录。

---

### /gitcommit — 质量门禁提交

**调用**: `/gitcommit` 或说"提交代码" | gitcommit-agent 并行跑 tester + quality-engineer，通过后写 `.claude/pass/*.pass` 标记文件，全部通过则调 `/git-save` 提交推送。`.githooks/pre-commit` 兜底拦截终端里的 `git commit`。

### 🏋️ 压力测试

```bash
locust -f tests/locustfile.py --host=http://localhost:8000
# → http://localhost:8089 设置并发数
```

---

## 开发注意事项

- 所有 API 请求（除 login/register/health）都需要 `Authorization: Bearer <token>` 头。
- Chat 接口是 SSE 流式响应，`curl` 需要 `--no-buffer`，前端使用 `EventSource` 或 `fetch` + `ReadableStream`。
- 文档入库是异步后台任务，上传后需轮询状态确认完成。
- 修改 RAG 参数（chunk_size、chunk_overlap、top_k 等）在 `backend/rag/pipeline.py` 和 `backend/rag/splitter.py` 中。
- ChromaDB 使用持久化模式，数据在 `data/chroma/`，清空此目录可重置所有向量数据。
- `.env` 中的 `DASHSCOPE_API_KEY` 必须有效才能使用 embedding 和 LLM 生成。
- SQLite 在 `backend/db/database.py` 中通过 `@connect` 事件设置 `busy_timeout=5000` + `journal_mode=WAL`，确保并发写入时等待而非报错。
