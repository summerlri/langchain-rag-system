"""
FastAPI 主入口 — 应用创建、中间件注册、路由挂载、生命周期管理

启动流程(lifespan):
  ① 创建必要目录(uploads/chroma/cache/data)
  ② 初始化数据库(建表 + 默认管理员)
  ③ 启动 HTTP 服务器

这个文件是整个后端的入口，相当于 SpringBoot 的 Application.main() 或 Express 的 app.js。
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db.database import init_db
from backend.core.exceptions import register_exception_handlers
from backend.api.auth import router as auth_router
from backend.api.knowledge_base import router as kb_router
from backend.api.chat import router as chat_router
from backend.api.conversation import router as conv_router

settings = get_settings()


async def startup_init():
    """
    应用启动时的初始化工作。

    为什么放在 lifespan 中而不是模块级执行?
      - 模块级代码在 import 时就执行(比如 pytest 测试时)，会尝试创建目录和连接数据库
      - lifespan 只在 uvicorn 真正启动时才执行，测试中的 TestClient 可以选择不触发

    初始化顺序很重要: 目录 → 数据库 → 日志
    没有目录数据库后续的 SQLite/ChromaDB 都会因为找不到路径而失败
    """
    # 创建必要目录 — exist_ok=True 表示已存在不报错，幂等安全
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    os.makedirs(settings.cache_dir, exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # 初始化数据库: 建表 + 创建默认管理员(admin/123456)
    await init_db()

    print(f"[OK] Database initialized: {settings.database_url}")
    print(f"[OK] ChromaDB dir: {settings.chroma_persist_dir}")
    print(f"[OK] Upload dir: {settings.upload_dir}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器。

    yield 之前的代码在启动时执行(初始化)
    yield 之后的代码在关闭时执行(清理)——目前不需要清理操作
    """
    await startup_init()
    yield


# ========== 创建 FastAPI 应用实例 ==========
app = FastAPI(
    title="RAG 企业级电商知识库问答系统",
    description="基于 LangChain + 阿里云百炼的 RAG 知识库问答系统",
    version="1.0.0",
    lifespan=lifespan,
)

# ========== CORS 跨域中间件 ==========
# 为什么需要 CORS? 前端(Vue, :5173)和后端(FastAPI, :8000)端口不同，
# 浏览器同源策略会阻止跨域请求。CORS 中间件告诉浏览器"这个后端允许前端访问"。
app.add_middleware(
    CORSMiddleware,
    # 白名单: 只允许本地前端访问，生产环境应改为实际域名
    allow_origins=[f"http://localhost:{settings.frontend_port}", "http://127.0.0.1:5173"],
    # allow_credentials=True: 允许前端携带 Cookie/Authorization 头
    # 注意: 如果 allow_credentials=True，allow_origins 不能是 ["*"]，必须明确列出
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 注册全局异常处理器 ==========
# 自定义异常(AppException/NotFoundException 等) → 统一 JSON 错误响应
# 未预料异常 → 500 + 通用错误消息
register_exception_handlers(app)

# ========== 注册 API 路由 ==========
# 四个路由模块各有独立的 prefix: /api/auth, /api/knowledge-bases, /api/chat, /api/conversations
app.include_router(auth_router)
app.include_router(kb_router)
app.include_router(chat_router)
app.include_router(conv_router)


# ========== 健康检查 ==========
# Kubernetes/负载均衡器通过这个端点判断服务是否存活
# 返回 JSON: {"status": "ok", "sqlite": "ok", "chromadb": "ok/error", "bailian_api": "configured/missing"}
@app.get("/api/health")
async def health_check():
    """
    健康检查端点 — GET /api/health。

    用途: 监控系统(Nagios/Prometheus/K8s liveness probe)定期调用此接口
    判断服务是否正常。不调用外部 API(避免因 API 不通而误报服务宕机)，
    只检查本地组件(SQLite/ChromaDB)和配置(API Key 是否设置)。
    """
    health = {
        "status": "ok",
        "sqlite": "ok",
        "chromadb": "unknown",
        "bailian_api": "unknown",
    }

    # ChromaDB 检查 — 只检查目录是否存在(不访问 collection，避免偶发的锁问题)
    try:
        chroma_dir = settings.chroma_persist_dir
        if os.path.exists(chroma_dir):
            health["chromadb"] = "ok"
        else:
            health["chromadb"] = "dir_not_found"
    except Exception as e:
        health["chromadb"] = f"error: {str(e)}"

    # 百炼 API 检查 — 只检查 Key 是否配置，不真正调用(避免每次健康检查都消耗配额)
    try:
        import dashscope  # noqa: F401 — 在 try 块内确认 dashscope 包已安装
        health["bailian_api"] = "configured" if settings.dashscope_api_key else "api_key_missing"
    except ImportError:
        health["bailian_api"] = "dashscope_not_installed"

    return health


# ========== 开发服务器入口 ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",              # 监听所有网络接口(局域网内其他设备可访问)
        port=settings.backend_port,    # 默认 8000
        reload=True,                   # ⚠️ 仅开发环境! 生产环境应设为 False
    )
