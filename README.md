# 🧠 RAG 企业级电商知识库问答系统

基于 **LangChain + FastAPI + ChromaDB + Vue 3** 的企业级 RAG（检索增强生成）知识库问答系统，面向电商场景。上传产品手册、FAQ、政策文档后，用户可以用自然语言提问，系统自动检索相关知识并用 AI 生成准确回答。

## ✨ 功能特性

- 🔐 **用户认证** — JWT 登录/注册/个人信息管理
- 📚 **知识库管理** — 创建知识库、上传文档（PDF/Word/Excel/Markdown）、自动分块入库
- 💬 **AI 问答** — 基于 RAG 的流式问答，可结合最近对话改写追问，打字机效果实时输出
- 🔍 **混合检索** — 语义、关键词与 MMR 多路召回并重排，结果带来源标注
- 📝 **对话管理** — 保存/切换/删除历史对话会话
- 📥 **对话导出** — 一键导出对话为 Markdown 文件，含引用来源标注
- ⚡ **两级缓存** — L1 内存 LRU + L2 diskcache，加速高频问答
- 🔒 **质量门禁** — 提交前自动运行测试 + 安全审计，通过才放行
- 🐳 **一键启动** — `start.bat` 自动初始化数据库 + 生成测试数据 + 启动前后端

## 🛠 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **LLM** | 通义千问 qwen-plus | 阿里云百炼 DashScope |
| **Embedding** | text-embedding-v2 | 文本向量化 |
| **后端框架** | FastAPI + Uvicorn | 异步 Python Web 框架 |
| **RAG 框架** | LangChain | 文档加载/分割/检索/生成 |
| **向量数据库** | ChromaDB | 持久化向量存储 |
| **关系数据库** | SQLite + SQLAlchemy | 用户/知识库/会话数据 |
| **前端** | Vue 3 + Element Plus + Vite | SPA 单页应用 |
| **认证** | JWT + bcrypt | 无状态认证 + 密码哈希 |

## 📁 项目结构

```
├── backend/                  # Python 后端
│   ├── api/                  # REST API 路由
│   │   ├── auth.py           # 登录/注册/用户管理
│   │   ├── chat.py           # SSE 流式问答
│   │   ├── conversation.py   # 对话会话管理
│   │   └── knowledge_base.py # 知识库 CRUD + 文档上传
│   ├── rag/                  # RAG 流水线
│   │   ├── loader.py         # 文档加载器（PDF/Word/Excel/MD）
│   │   ├── splitter.py       # 文本分割器
│   │   ├── embedding.py      # 百炼 Embedding 封装
│   │   ├── vector_store.py   # ChromaDB 向量存储
│   │   ├── retriever.py      # 混合检索器（语义 + 关键词 + MMR + RRF）
│   │   ├── chain.py          # RAG Prompt 模板
│   │   └── pipeline.py       # 完整问答流水线
│   ├── models/               # SQLAlchemy ORM 模型
│   ├── core/                 # JWT 安全 / 依赖注入 / 异常处理
│   ├── cache/                # L1+L2 两级缓存
│   ├── db/                   # 数据库初始化
│   ├── schemas/              # Pydantic 请求/响应模型
│   └── config.py             # 配置管理
├── frontend/                 # Vue 3 前端
│   └── src/
│       ├── views/            # 页面组件
│       │   ├── Chat.vue      # 问答对话页
│       │   ├── KnowledgeBase.vue # 知识库管理页
│       │   ├── Login.vue     # 登录页
│       │   ├── Register.vue  # 注册页
│       │   └── Profile.vue   # 个人中心页
│       ├── api/              # Axios API 封装
│       ├── stores/           # Pinia 状态管理
│       └── router/           # Vue Router 路由
├── scripts/seed_data.py      # 生成电商测试知识库文档
├── tests/                    # 单元测试 + API 测试 + RAG 测试
├── data/                     # 运行时数据（数据库/向量/缓存/上传文件）
├── start.bat                 # Windows 一键启动脚本
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量模板
└── CLAUDE.md                 # AI 助手指南
```

## 🚀 快速启动

### 前置要求

- **Python** >= 3.10
- **Node.js** >= 18（前端）
- **阿里云百炼 API Key**（[免费申请](https://bailian.console.aliyun.com/)）

### 1. 克隆项目

```bash
git clone https://github.com/summerlri/langchain-rag-system.git
cd langchain-rag-system
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入你的百炼 API Key：

```env
DASHSCOPE_API_KEY=sk-your-real-key-here
```

### 3. 安装后端依赖

```bash
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

### 4. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 5. 初始化数据库 + 生成测试数据

```bash
python -m backend.db.init_db
python scripts/seed_data.py
```

### 6. 启动服务

```bash
# Windows 一键启动
start.bat

# 或手动分别启动
# 终端 1: 后端
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2: 前端
cd frontend && npm run dev
```

- **后端**: http://localhost:8000
- **API 文档（Swagger）**: http://localhost:8000/docs
- **前端**: http://localhost:5173

## 📖 使用指南

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `123456` | 管理员 |

> ⚠️ 生产环境请务必修改默认密码！

### 基本流程

1. **登录** → 访问 http://localhost:5173 → 用 `admin/123456` 登录
2. **创建知识库** → 进入"知识库管理" → 新建知识库
3. **上传文档** → 在知识库中上传 PDF/Word/Excel/Markdown 文档
4. **等待入库** → 文档状态变为"已完成"即可
5. **开始问答** → 进入"AI 问答" → 选择知识库 → 输入问题

### 生成测试数据

```bash
python scripts/seed_data.py
```

会在 `data/seed_docs/` 生成 3 个电商测试文档：
- 电商平台商品知识库
- 手机通讯产品手册
- 常见问题 FAQ

在管理后台上传这些文档，即可测试 RAG 问答效果。

### 测试问题示例

| 问题 | 预期会检索到的内容 |
|------|-------------------|
| "iPhone 15 Pro Max 的售价是多少？" | 价格信息（¥9,999） |
| "华为 Mate 60 Pro 有什么特色功能？" | 卫星通话等 |
| "如何退货？" | 退换货政策 |

## ⚙️ 配置说明

`.env` 文件中的主要配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key（必填） | - |
| `QWEN_MODEL` | 对话模型 | `qwen-plus` |
| `EMBEDDING_MODEL` | 文本嵌入模型 | `text-embedding-v2` |
| `DATABASE_URL` | SQLite 数据库路径 | `sqlite+aiosqlite:///./data/rag.db` |
| `CHROMA_PERSIST_DIR` | ChromaDB 向量存储目录 | `./data/chroma` |
| `UPLOAD_DIR` | 文档上传目录 | `./data/uploads` |
| `CACHE_DIR` | 缓存目录 | `./data/cache` |
| `JWT_SECRET_KEY` | JWT 签名密钥（生产环境必须修改） | - |
| `BACKEND_PORT` | 后端端口 | `8000` |
| `FRONTEND_PORT` | 前端端口 | `5173` |

> 💡 **并发优化**: SQLite 通过 `busy_timeout=5000` + `journal_mode=WAL` + 连接池，支持 100 人并发写入（详见 `backend/db/database.py`）。

## 🧪 运行测试

### 单元测试 + 覆盖率

```bash
pytest tests/ -v --cov=backend --cov-report=html:reports/coverage
pytest tests/unit/ -v   # 仅单元测试
pytest tests/api/ -v     # 仅 API 测试
pytest tests/rag/ -v     # 仅 RAG 流水线测试
```

报告输出在 `reports/` 目录下。

### 压力测试（Locust）

模拟 100 人同时使用系统：

```bash
pip install locust
locust -f tests/locustfile.py --host=http://localhost:8000
```

浏览器打开 http://localhost:8089，设置并发用户数。测试脚本包含 3 个场景：浏览知识库、AI 问答、导出对话。

## 📄 License

MIT
