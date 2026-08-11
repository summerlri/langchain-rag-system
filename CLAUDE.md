# CLAUDE.md

## 项目简介

知问台是一个基于 LangChain、FastAPI、ChromaDB 和 Vue 3 的 RAG 知识库，支持多轮追问、语义与关键词混合检索、来源引用和 SSE 流式回答。

## 技术与入口

- Python 3.11 推荐，最低 3.10；前端使用 Node.js 18+。
- 后端：http://localhost:8000；健康检查：`GET /api/health`。
- 前端：http://localhost:5173；默认本地账号：`admin / 123456`。
- 登录接口接收 JSON：`{"username":"admin","password":"123456"}`。
- 真实问答需要 `.env` 中有效的 `DASHSCOPE_API_KEY`。

## 重要目录

```text
backend/api/          认证、知识库、会话和 SSE 聊天接口
backend/rag/          加载、切分、向量、混合检索与问答流水线
frontend/src/         Vue 3 前端
tests/                unit、api、rag 和 Locust 测试
scripts/rag_ops.py    真实诊断、入库和 RAG 冒烟测试
.claude/agents/       组合任务的子代理
.claude/commands/     可直接调用的确定性命令
.githooks/            与当前暂存差异绑定的提交门禁
```

## 命令

- `/test [all|unit|api|rag|coverage]`：运行自动化测试。
- `/rag-ingest <文件>`：真实上传并等待文档入库。
- `/rag-smoke-test`：执行三条知识问答和一条多轮追问；会调用百炼 API。
- `/rag-debug`：检查 API、SQLite、ChromaDB、缓存和失败文档；默认不调用外部 API。
- `/security-audit [路径]`：只读安全检查。

## 子代理职责

- `rag-debugger`：组合本地诊断并解释 RAG 故障。
- `quality-reviewer`：根据暂存文件类型选择检查，不无差别扫描全项目。
- `commit-gate`：显式暂存文件，并行协调测试与质量审查；只有用户要求时才推送。

## 开发规则

- API 除登录、注册和健康检查外均需要 Bearer Token。
- 文档入库在后台执行，上传后必须轮询到 `completed` 或 `failed`。
- Chat 使用 SSE；测试时必须解析 `rewrite`、`sources`、`token`、`done` 和 `error` 事件。
- RAG 单元测试使用 Mock，不得把它描述成真实百炼或真实 ChromaDB 全链路测试。
- SQLite 的 WAL 和 `busy_timeout` 只能改善本地并发，不代表固定并发容量。
- `.env`、`.claude/settings.local.json`、运行数据和质量标记不得提交。

## 提交门禁

1. 只暂存当前任务涉及的文件，禁止 `git add .`。
2. 测试与质量审查标记必须包含当前暂存差异的 SHA-256 和 UTC 时间。
3. 标记有效期为 30 分钟；暂存内容变化后自动失效。
4. 提交完成后删除 `.claude/pass/test.pass` 和 `quality.pass`。
