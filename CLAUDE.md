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

**用途**: 通过命令行快速将一个文档上传到知识库并等待入库完成，适合测试分割/embedding 策略时使用。

**调用方式**: `/rag-ingest <文件路径>`

**执行步骤**:

1. **检查服务状态** — 先请求 `GET http://localhost:8000/api/health` 确认后端已启动。如果未启动，提示用户先运行 `/rag-start` 或 `start.bat`。

2. **登录获取 Token** — 发送:
   ```
   POST http://localhost:8000/api/auth/login
   Content-Type: application/json
   {"username":"admin","password":"123456"}
   ```
   从响应的 `access_token` 字段提取 JWT token。

3. **获取或创建知识库** — 用 Bearer token 请求 `GET http://localhost:8000/api/knowledge-bases`。如果没有知识库，自动创建一个名为 "默认知识库" 的知识库:
   ```
   POST http://localhost:8000/api/knowledge-bases
   {"name": "默认知识库", "description": "自动创建的知识库"}
   ```

4. **上传文档** — 用 curl 的 `-F` 上传文件:
   ```
   POST http://localhost:8000/api/knowledge-bases/{kb_id}/documents
   Authorization: Bearer <token>
   Content-Type: multipart/form-data
   file=@<文件路径>
   ```

5. **轮询入库状态** — 上传后每 2 秒检查文档状态:
   ```
   GET http://localhost:8000/api/knowledge-bases/{kb_id}/documents
   ```
   找到对应文档，检查 `status` 字段：`processing` → 继续等待，`completed` → 成功，`failed` → 报告错误。

6. **报告结果** — 显示: 文档名、chunk 数量、入库耗时。

---

### /rag-test — RAG 冒烟测试

**用途**: 代码改动后，执行一次完整的 RAG 问答链路测试，快速验证整套系统是否工作正常。

**调用方式**: `/rag-test`

**测试用例**:
| 问题 | 预期 |
|------|------|
| "iPhone 15 Pro Max 的售价是多少？" | 应检索到相关 chunk，回答中包含 ¥9,999 等价格信息 |
| "华为 Mate 60 Pro 有什么特色功能？" | 应检索到相关 chunk，回答中包含卫星通话等 |
| "如何退货？" | 应检索到退换货政策相关 chunk |

**执行步骤**:

1. **健康检查** — `GET http://localhost:8000/api/health`，确认所有组件状态为 ok。

2. **登录** — 同 `/rag-ingest`，获取 token。

3. **确保有知识库且已入库文档** — `GET http://localhost:8000/api/knowledge-bases`。检查至少有一个知识库且 `doc_count > 0`。如果 doc_count 为 0，提示用户先运行 `python scripts/seed_data.py` 然后在管理后台手动上传 `data/seed_docs/` 中的文档。

4. **创建测试会话** — `POST http://localhost:8000/api/conversations`，body: `{"kb_id": "<kb_id>", "title": "RAG冒烟测试"}`。

5. **发送测试问题** — 对上面 3 个测试问题依次发送:
   ```
   POST http://localhost:8000/api/chat/{conv_id}
   Authorization: Bearer <token>
   Content-Type: application/json
   {"message": "<问题>", "kb_id": "<kb_id>"}
   ```
   这个接口返回 SSE 流 (`text/event-stream`)，需要解析 SSE 事件:
   - `type: "sources"` → 提取检索到的文档 chunk 数量和内容
   - `type: "token"` → 拼接为完整回答文本
   - `type: "done"` → 获取 `total_tokens` 和 `latency_ms`

   对于 curl，使用 `--no-buffer` 参数来获取流式输出。

6. **评估结果** — 对每个测试问题报告:
   - ✅/❌ 是否检索到相关文档
   - ✅/❌ 回答是否包含预期信息
   - 生成耗时（ms）和 token 用量

7. **总结** — 汇总通过率（如 "3/3 全部通过 ✅" 或 "2/3 通过，1 个失败"）。

---

### /rag-debug — RAG 调试面板

**用途**: 检查系统各组件的运行状态，快速定位问题环节。

**调用方式**: `/rag-debug`

**诊断维度**:

1. **后端服务** — `GET http://localhost:8000/api/health`，报告:
   - FastAPI 服务状态
   - SQLite 数据库状态
   - ChromaDB 状态
   - 百炼 API Key 配置状态

2. **向量数据库 (ChromaDB)** — 检查 `data/chroma/` 目录:
   - 列出所有 collection（每个 collection 对应一个知识库）
   - 每个 collection 的文档 chunk 数量
   - 使用 Python 脚本检测:
     ```python
     import chromadb
     client = chromadb.PersistentClient(path="./data/chroma")
     for col in client.list_collections():
         count = col.count()
         print(f"  Collection '{col.name}': {count} chunks")
     ```

3. **关系数据库 (SQLite)** — 检查 `data/rag.db`:
   - 用户数量
   - 知识库数量
   - 文档数量（按状态分类: pending/processing/completed/failed）
   - 会话和消息数量

4. **缓存状态** — 检查 `data/cache/` 目录:
   - 缓存文件大小
   - 缓存条目数（如果可读取 diskcache）

5. **Embedding 连通性** — 用 Python 测试百炼 Embedding API 是否可达:
   ```python
   from backend.rag.embedding import BailianEmbeddings
   emb = BailianEmbeddings()
   result = emb.embed_query("测试连通性")
   print(f"Embedding 维度: {len(result)}, 连通性: OK")
   ```

6. **最近错误日志** — 检查数据库中 status=failed 的文档记录，报告失败原因。

7. **诊断总结** — 用表格汇总所有检查项，每个标记 ✅/⚠️/❌，有问题的给出修复建议。

---

### /make-tests — 单元测试生成与执行

**用途**: 对项目代码自动生成/运行单元测试，并生成 HTML 测试报告。适用于代码改动后验证、CI/CD 前的质量检查。

**调用方式**: `/make-tests [选项]`

**选项**:
- 无参数 — 执行全部测试
- `unit` — 仅执行单元测试（fast，无需外部服务）
- `api` — 仅执行 API 集成测试
- `rag` — 仅执行 RAG 流水线测试
- `coverage` — 仅生成覆盖率报告
- `add <文件路径>` — 为指定源文件生成新的测试文件

**测试结构**:

```
tests/
├── conftest.py               # 共享 fixtures: mock DB、mock embedding、mock LLM 等
├── unit/                     # 单元测试（毫秒级，纯逻辑，mock 全部外部依赖）
│   ├── test_security.py      # JWT + 密码哈希
│   ├── test_splitter.py      # 文本分割器
│   ├── test_loader.py        # 文档加载器
│   ├── test_cache.py         # 两级缓存
│   ├── test_schemas.py       # Pydantic 校验
│   └── test_chain.py         # RAG Prompt 组装
├── api/                      # API 集成测试（SQLite 内存库，模拟 HTTP 请求）
│   ├── test_auth.py          # 注册/登录/修改密码/获取用户
│   ├── test_knowledge_base.py # 知识库 CRUD（需管理员 Token）
│   └── test_conversation.py  # 会话 CRUD
└── rag/                      # RAG 流水线测试
    ├── test_retriever.py     # 检索器（mock ChromaDB）
    ├── test_pipeline.py      # 完整问答流水线（mock LLM + Embedding）
    └── test_loader.py        # 文档加载器（临时文件）
```

**执行步骤**:

1. **检查依赖** — 运行以下命令安装测试依赖:
   ```bash
   pip install pytest pytest-asyncio pytest-cov pytest-html -q
   ```
   如果已有则可以跳过。

2. **运行测试** — 根据选项执行不同的测试子集:
   ```bash
   # 全部测试 + 覆盖率 + HTML 报告
   pytest tests/ -v --tb=short --cov=backend --cov-report=html:reports/coverage --cov-report=term-missing --html=reports/test_report.html --self-contained-html

   # 仅单元测试
   pytest tests/unit/ -v -m unit

   # 仅 API 测试
   pytest tests/api/ -v -m api

   # 仅 RAG 测试
   pytest tests/rag/ -v -m rag

   # 仅覆盖率
   pytest tests/ --cov=backend --cov-report=html:reports/coverage --cov-report=term-missing
   ```

3. **检查报告** — 测试完成后:
   - **HTML 报告**: 位于 `reports/test_report.html`，用浏览器打开可查看交互式测试结果
   - **覆盖率报告**: 位于 `reports/coverage/index.html`，可查看每行代码的覆盖情况
   - **终端输出**: 显示通过的测试数量和失败详情

4. **自动生成新测试** — 当使用 `/make-tests add <文件路径>` 时:
   - 分析目标文件的函数签名、类方法、分支逻辑
   - 参考 `tests/` 中已有的测试模式
   - 在对应目录生成 test_*.py 文件
   - 确保使用 `conftest.py` 中已有的 fixtures 和 mock

5. **报告汇总** — 输出:
   - 📊 总测试数 / 通过数 / 失败数 / 跳过数
   - 🐌 最慢的 10 个测试
   - 📈 代码覆盖率百分比
   - 🔗 报告文件路径

**Mock 策略**:

| 被测层 | Mock 了什么 | 为什么 |
|--------|------------|--------|
| 单元测试 | 无外部依赖 | 纯逻辑：密码哈希、文本分割、Pydantic 校验 |
| API 测试 | SQLite 内存库 + mock ChromaDB | 不需要真实数据库文件，测试完自动销毁 |
| RAG 测试 | LLM (Tongyi)、Embedding (Bailian)、ChromaDB | 不消耗 API 额度，结果确定可复现 |

---

### /security-audit — 安全审计

**用途**: 对项目进行全面的代码安全审计，检测敏感信息泄露、注入漏洞、配置风险、依赖漏洞等。适用于代码审查、上线前安全检查、安全合规检查。

**调用方式**: `/security-audit [路径]`

**参数**:
- 无参数 — 审计 `backend/` 下所有 Python 文件 + 配置文件（`.env`、`.toml`、`.yaml` 等）
- `<文件路径>` — 仅审计指定文件
- `<目录路径>` — 审计指定目录下所有文件

**五大审计维度**:

### 🔴 维度一：硬编码敏感信息泄露

检查代码中是否直接写入了：

| 类型 | 检测正则 | 示例 |
|------|----------|------|
| API Key / Token | `sk-`、`api_key\s*=`、`Bearer` | `DASHSCOPE_API_KEY=sk-` |
| 密码 / 口令 | `password\s*=`、`passwd\s*=`、`hashed_password` | `"123456"`、`"admin123"` |
| JWT 签名密钥 | `secret_key\s*=`、`jwt_secret` | `"change-this-"` ← 默认值不安全 |
| 数据库连接串（含密码） | `mysql://`、`postgresql://`、`mongodb://` | `mysql://root:123456@` |
| 私钥 / 证书 | `-----BEGIN RSA PRIVATE KEY-----`、`.pem` | PEM 格式密钥 |

严重度判定：
- 🚨 严重：发现真实 API Key、生产密码（如 `.env` 中有真正的 `sk-` key）
- 🔴 高风险：默认密码/密钥未修改（如 `jwt_secret_key: change-this-...`）
- 🟡 中风险：密码哈希值暴露在代码中（可离线暴力破解）

### 🔴 维度二：注入漏洞

检查是否存在以下注入风险：

**SQL 注入**：
- 检测是否使用字符串拼接构造 SQL（如 `f"SELECT * FROM {table}"`、`"SELECT " + col`）
- 检测是否使用 `.format()` 或 `%` 格式化 SQL 语句
- 确认是否所有数据库操作都使用 ORM 参数化查询（本项目使用 SQLAlchemy，应全部用 `select().where()` 模式）

**命令注入**：
- 检测 `os.system()`、`os.popen()`、`subprocess.call(shell=True)` 的调用
- 检测参数是否由用户输入拼接而来
- 检测 `eval()`、`exec()` 的使用（几乎永远不应该出现）

**路径遍历**：
- 检测文件操作中是否直接使用用户输入构造路径
- 尤其是 `os.path.join(user_input, ...)` 模式，检查是否对 `../` 做了过滤
- 检测文件上传功能中是否保留了原始文件名

严重度判定：
- 🚨 严重：直接拼接用户输入到 SQL/命令中
- 🔴 高风险：文件路径使用用户输入未过滤
- 🟡 中风险：使用了 `shell=True` 但参数硬编码

### 🔴 维度三：配置文件敏感信息

检查 `.env`、`.toml`、`.yaml`、`config.py`、`settings.py` 等配置文件：

- `.env` 中是否包含**真实的 API Key**（非占位符 `xxx` 的那种）
- `.env` 是否已被 `.gitignore` 忽略（如果已提交到 Git，视为泄露）
- `config.py` 中的默认值是否包含真实的密钥/密码
- JWT Secret / Session Secret 是否使用了弱密钥
- 数据库连接字符串是否包含了密码
- 第三方服务 credential 是否硬编码在配置文件中

严重度判定：
- 🚨 严重：发现真实的（非占位）生产密钥
- 🔴 高风险：`.env` 被提交到 Git（检查 `git log -- .env`）
- 🟡 中风险：默认密钥未修改为生产值

### 🟡 维度四：认证与授权缺陷

- JWT Token 过期时间是否合理（过长 = 风险）
- 密码哈希算法是否安全（bcrypt ✅ / MD5 ❌ / SHA1 ❌）
- 是否存在绕过认证的风险（如 debug 模式下跳过验证）
- CORS 配置是否过于宽松（`allow_origins=["*"]`）
- 敏感 API（如管理员接口）是否做了权限校验

### 🟡 维度五：依赖与运行时风险

- 检查 `requirements.txt` / `pyproject.toml` 中是否有已知漏洞的依赖版本
- 检查是否使用了已弃用的不安全函数（如 `pickle.load()` 未限制类型）
- 日志中是否可能记录敏感信息（密码、Token 等）
- HTTPS 是否强制启用（生产环境）

**执行步骤**:

1. **收集目标文件** — 根据参数确定审计范围：
   ```bash
   # Python 源码
   find <target> -name "*.py" -not -path "*/tests/*" -not -path "*/venv/*" | sort
   # 配置文件
   find <project_root> -maxdepth 1 -name ".env" -o -name "*.toml" -o -name "*.yaml" -o -name "*.yml" 2>/dev/null
   ```
   默认范围：`backend/**/*.py` + 项目根目录配置文件。

2. **逐维度扫描** — 对每个文件执行五大维度检查：
   - 使用 Grep 匹配敏感信息正则模式（API Key、密码、Token）
   - 使用 Read 读取文件内容，检查 SQL 拼接、命令注入、路径遍历
   - 读取配置文件，逐行检查敏感值
   - 检查 `.gitignore` 确认 `.env` 是否被排除
   - 运行 `git log --oneline -- .env` 检查是否曾提交到 Git

3. **检查 .gitignore** — 确认敏感文件是否在 gitignore 中:
   ```bash
   grep -n ".env" .gitignore
   ```

4. **生成审计报告** — 按严重程度排序：

   ```
   🔒 安全审计报告
   ══════════════
   审计时间: 2026-08-06
   审计范围: backend/ + 配置文件 (22 个文件)

   🚨 严重问题 (必须立即修复)
   ┌────┬──────────────────┬──────────────────────────────────────┐
   │ #  │ 位置             │ 问题                                 │
   ├────┼──────────────────┼──────────────────────────────────────┤
   │ 1  │ .env:3           │ 🚨 真实 API Key 泄露！              │
   │    │                  │ DASHSCOPE_API_KEY=sk-ws-H.EHMI...   │
   │    │                  │ 应立即轮换此 Key，并从文件中删除     │
   ├────┼──────────────────┼──────────────────────────────────────┤
   │ 2  │ backend/db/      │ 🚨 默认密码硬编码                   │
   │    │ init_db.py:26    │ hash_password("123456")             │
   │    │                  │ 应改为首次启动时生成随机密码          │
   └────┴──────────────────┴──────────────────────────────────────┘

   🔴 高风险问题
   ┌────┬──────────────────┬──────────────────────────────────────┐
   │ 3  │ backend/config   │ 🔴 JWT 密钥使用弱默认值              │
   │    │ .py:22           │ jwt_secret_key = "change-this-..."   │
   │    │                  │ 应从环境变量读取，拒绝默认值启动      │
   ├────┼──────────────────┼──────────────────────────────────────┤
   │ 4  │ backend/config   │ 🔴 API Key 有默认占位值              │
   │    │ .py:11           │ dashscope_api_key = "sk-xxx..."      │
   │    │                  │ 应设为空或直接报错，不提供默认值       │
   └────┴──────────────────┴──────────────────────────────────────┘

   🟡 中风险问题
   ┌────┬──────────────────┬──────────────────────────────────────┐
   │ 5  │ backend/api/     │ 🟡 文件上传路径未充分过滤            │
   │    │ knowledge_base   │ safe_filename = f"{doc_id}_{file    │
   │    │ .py:182          │ .filename}" — 应使用 sanitize 函数   │
   ├────┼──────────────────┼──────────────────────────────────────┤
   │ 6  │ backend/main.py  │ 🟡 CORS 配置范围较宽                 │
   │    │ :52              │ allow_methods=["*"]                 │
   │    │                  │ 应限制为具体方法列表                  │
   └────┴──────────────────┴──────────────────────────────────────┘

   ✅ 通过的检查
   - SQL 注入：全部使用 ORM 参数化查询，无字符串拼接 SQL
   - 命令注入：未发现 os.system / eval / exec 使用
   - 密码哈希：使用 bcrypt（安全）
   - 依赖安全：无已知漏洞版本

   📋 修复优先级
   1. 🚨 立即轮换 .env 中的 API Key（已在代码仓库中暴露）
   2. 🚨 移除 init_db.py 中的硬编码默认密码
   3. 🔴 拒绝 JWT_SECRET_KEY 的默认值启动
   4. 🔴 确保 .env 在 .gitignore 中
   5. 🟡 文件上传文件名做 sanitize
   ```

5. **输出修复建议** — 每个问题附具体修复代码示例：

   ```
   🚨 问题 #1: .env API Key 泄露
   修复步骤:
   1. git rm --cached .env（如果已提交到 Git）
   2. 在百炼控制台重新生成新 Key
   3. 更新 .env 为新 Key
   4. 确认 .gitignore 包含 .env
   ```

**注意事项**:
- 🚨 发现真实 API Key 时必须用 `****` 遮掩部分内容后再输出报告
- 审计结果中的敏感值（如 Key 的后半段）只显示前 8 位字符 + `****`
- 本技能**只做检查和建议**，不自动修改任何文件
- 检查 `.env` 是否在 `.gitignore` 中，如不在则标记为高风险
- 默认排除 `venv/`、`node_modules/`、`__pycache__/`、`tests/`、`.git/`

---

### /comments-check — 代码注释质量检查

**用途**: 全面检查项目代码的注释质量，从三个维度评估：注释覆盖率、注释准确性、注释可读性。适用于代码审查、新人入职代码熟悉、交付前质量检查。

**调用方式**: `/comments-check [路径]`

**参数**:
- 无参数 — 检查 `backend/` 下所有 Python 文件
- `<文件路径>` — 检查指定文件，如 `/comments-check backend/rag/pipeline.py`
- `<目录路径>` — 检查指定目录，如 `/comments-check backend/api/`

**三个检查维度**:

### 维度一：注释覆盖率（Comments Coverage）

检查代码中注释行与代码行的比例，目标是 **30% 注释率**（约每 10 行中 3 行注释、7 行代码）。

检查规则：
- 统计每个文件的：总行数、注释行数（`#` 开头或 `"""..."""` 文档字符串）、代码行数
- 计算注释率 = 注释行数 / 总行数
- 检查每个函数/方法是否至少有一行 docstring 或注释说明其用途
- 检查核心逻辑（10 行以上的函数体、复杂条件分支、正则表达式、算法实现等）是否有行内注释

打分标准：
- 🟢 优秀：文件注释率 ≥ 30%，且每个函数都有 docstring
- 🟡 一般：20% ≤ 注释率 < 30%，或个别函数缺少说明
- 🔴 不足：注释率 < 20%，或多个核心函数无注释

### 维度二：注释准确性（Comments Accuracy）

检查注释内容是否与代码实际逻辑匹配，防止"注释说一套代码做一套"。

检查规则：
- 函数 docstring 描述的入参/出参是否与函数签名一致
- 注释描述的业务逻辑是否与实际代码一致
- 是否存在"过时注释"（代码已修改但注释未更新）
- 是否存在"错误注释"（注释描述了相反的逻辑）

检查方法：
- 读取函数注释，提取关键描述词
- 对照代码实际逻辑（函数名、参数、返回值类型、核心条件判断）
- 标记不匹配之处

打分标准：
- 🟢 准确：所有注释与代码一致
- 🟡 可疑：存在 1-2 处不明确的描述
- 🔴 错误：存在明显矛盾（如注释说"升序排列"但代码是 `reverse=True`）

### 维度三：注释可读性（Comments Readability — 小白视角）

检查注释是否以**非专业开发者视角**也能看懂。要求避免纯技术黑话，用通俗语言解释"为什么这样做"。

检查规则：
- 注释是否解释了**为什么**（why），而不仅仅是**做了什么**（what）
- 是否避免了未经解释的缩写或术语（如仅写 "MMR" 而未解释是 Max Marginal Relevance）
- 复杂逻辑是否有"翻译成人话"的注释
- 业务相关代码是否有对应业务含义的注释（如"满 300 减 50"而非仅写"discount_rule = 1"）

打分标准：
- 🟢 小白友好：用通俗语言解释了为什么和怎么做
- 🟡 偏技术：能看懂但需要一定背景知识
- 🔴 天书：纯技术术语堆砌，业务人员无法理解

**执行步骤**:

1. **确定扫描范围** — 根据参数确定要检查的文件列表（默认 `backend/**/*.py`，排除 `tests/` 和 `venv/`）

2. **逐文件扫描分析** — 对每个 Python 文件执行三维度检查：
   - 使用 Glob 找到所有 `.py` 文件
   - 使用 Read 读取文件内容
   - 统计注释行数、识别所有函数/方法、提取 docstring
   - 对照代码逻辑检查注释准确性
   - 评估注释语言的可读性

3. **生成检查报告** — 按文件汇总，包含：

   ```
   📋 注释质量检查报告
   ====================

   📊 总体统计
   ├── 扫描文件数: X 个
   ├── 总代码行数: X 行
   ├── 总注释行数: X 行
   ├── 整体注释率: XX%
   ├── 🟢 优秀文件: X 个
   ├── 🟡 一般文件: X 个
   └── 🔴 不足文件: X 个

   📁 逐文件详情（按严重程度排序）

   ## backend/api/chat.py — 🔴 注释率 3%
   | 维度 | 评分 | 问题 |
   |------|------|------|
   | 覆盖率 | 🔴 不足 (3%) | 96 行代码仅 3 行注释，send_message 函数无 docstring |
   | 准确性 | 🟡 可疑 | 第 68 行注释"自动生成标题"但实际逻辑是取前30字符截断 |
   | 可读性 | 🔴 天书 | SSE 事件流处理逻辑完全无解释，新人无法理解 |

   ## backend/core/security.py — 🟢 注释率 35%
   | 维度 | 评分 | 问题 |
   |------|------|------|
   | 覆盖率 | 🟢 优秀 (35%) | 每个函数都有 docstring 和行内注释 |
   | 准确性 | 🟢 准确 | 注释与实际代码一致 |
   | 可读性 | 🟡 偏技术 | hash_password 缺少"为什么用 bcrypt"的业务说明 |

   💡 改进建议（Top 5）
   1. backend/api/chat.py: 为 send_message 添加 docstring
   2. backend/rag/pipeline.py: 为 RAGPipeline.query 添加详细的流式处理注释
   ...
   ```

4. **给出改进建议** — 按优先级排列：
   - 🔴 高优先级：核心 API 端点缺少注释
   - 🟡 中优先级：函数缺少 docstring 或注释不准确
   - 🟢 低优先级：注释可读性优化建议

**注意事项**:
- 跳过 `tests/`、`venv/`、`__pycache__/`、`node_modules/`
- 跳过仅包含 import / 常量定义 / 配置类的文件（不做强制注释率要求）
- 注释包含 `# TODO`、`# FIXME`、`# NOTE` 等标记时，标记为"占位注释"不作为有效注释
- 如果文件数量较多（>20），先做快速扫描统计注释率，对有问题的文件再深度检查

---

### /gitcommit — 质量门禁提交

**用途**: 提交代码前自动运行测试和质量检查，全部通过后才放行提交。代替直接 `git commit`。

**调用方式**: `/gitcommit` 或说"提交代码"

**流程**:
1. gitcommit-agent 并行启动 tester 和 quality-engineer
2. tester 运行全部测试 → 通过则写入 `.claude/pass/test.pass`
3. quality-engineer 审计安全/注释/规范 → 通过则写入 `.claude/pass/quality.pass`
4. 两个标记文件都存在 → 调用 `/git-save` 提交并推送
5. 任一失败 → 报告错误，拒绝提交

**Git 钩子**: `.githooks/pre-commit` 在 `git config core.hooksPath .githooks` 配置后生效，拦截终端里直接敲的 `git commit`。

### 🏋️ 压力测试

```bash
locust -f tests/locustfile.py --host=http://localhost:8000
```

浏览器打开 http://localhost:8089，设置并发用户数。3 个场景模拟真实用户行为（浏览/问答/导出）。

---

## 开发注意事项

- 所有 API 请求（除 login/register/health）都需要 `Authorization: Bearer <token>` 头。
- Chat 接口是 SSE 流式响应，`curl` 需要 `--no-buffer`，前端使用 `EventSource` 或 `fetch` + `ReadableStream`。
- 文档入库是异步后台任务，上传后需轮询状态确认完成。
- 修改 RAG 参数（chunk_size、chunk_overlap、top_k 等）在 `backend/rag/pipeline.py` 和 `backend/rag/splitter.py` 中。
- ChromaDB 使用持久化模式，数据在 `data/chroma/`，清空此目录可重置所有向量数据。
- `.env` 中的 `DASHSCOPE_API_KEY` 必须有效才能使用 embedding 和 LLM 生成。
- SQLite 在 `backend/db/database.py` 中通过 `@connect` 事件设置 `busy_timeout=5000` + `journal_mode=WAL`，确保并发写入时等待而非报错。
