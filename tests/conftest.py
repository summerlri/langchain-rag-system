"""
测试共享 Fixtures — 提供 mock object、测试数据库、FastAPI TestClient 等
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 预导入所有模型，确保 Base.metadata 在 db_session 建表前已注册所有表
import backend.models.user  # noqa: E402
import backend.models.knowledge_base  # noqa: E402
import backend.models.conversation  # noqa: E402


# ======================== 配置 Mock ========================

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """为所有测试自动提供测试环境变量，防止误操作真实数据和 API"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test-mock-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/test_rag.db")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", "./data/test_chroma")
    monkeypatch.setenv("UPLOAD_DIR", "./data/test_uploads")
    monkeypatch.setenv("CACHE_DIR", "./data/test_cache")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    # 清除 lru_cache，确保新的环境变量生效
    from backend.config import get_settings
    get_settings.cache_clear()


# ======================== 安全模块 ========================

@pytest.fixture
def sample_password():
    return "TestPass123!"


@pytest.fixture
def hashed_password(sample_password):
    from backend.core.security import hash_password
    return hash_password(sample_password)


@pytest.fixture
def valid_token(test_user):
    """生成与 test_user 匹配的 JWT token"""
    from backend.core.security import create_access_token
    return create_access_token(data={"sub": test_user.id, "username": test_user.username})


@pytest.fixture
def expired_token(test_user):
    """生成已过期的 JWT token"""
    from datetime import timedelta
    from backend.core.security import create_access_token
    return create_access_token(
        data={"sub": test_user.id, "username": test_user.username},
        expires_delta=timedelta(seconds=-1),
    )


# ======================== 数据库 ========================

@pytest.fixture
async def db_session(tmp_path):
    """
    创建测试数据库的异步会话。
    使用临时文件而非 :memory:，因为 SQLite :memory: 每个连接创建独立数据库，
    导致建表连接与会话连接不在同一数据库。
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    db_path = tmp_path / "test.db"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # 建表 —— 使用同一个引擎，确保连接池里的任何连接都指向同一个文件
    from backend.db.database import Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 提供会话
    async with TestSession() as session:
        yield session

    # 清理
    await test_engine.dispose()


# ======================== 用户 ========================

@pytest.fixture
async def test_user(db_session):
    """在测试数据库中创建一个普通用户"""
    from datetime import datetime
    from backend.models.user import User
    from backend.core.security import hash_password

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = User(
        id="test-user-id-001",
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("TestPass123!"),
        is_admin=0,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_admin(db_session):
    """在测试数据库中创建一个管理员用户"""
    from datetime import datetime
    from backend.models.user import User
    from backend.core.security import hash_password

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin = User(
        id="test-admin-id-001",
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("AdminPass123!"),
        is_admin=1,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(admin)
    await db_session.flush()
    return admin


# ======================== FastAPI TestClient ========================

@pytest.fixture
def app_with_mocked_db(db_session):
    """
    构建 FastAPI app 实例，用测试数据库会话替换依赖注入的 get_db。
    使用 app_with_mocked_db 可在不启动真实服务器的情况下测试 API。
    """
    from backend.main import app
    from backend.db.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app_with_mocked_db):
    """FastAPI TestClient — 可以直接对 API 发请求"""
    from fastapi.testclient import TestClient
    return TestClient(app_with_mocked_db)


# ======================== Mock RAG 组件 ========================

@pytest.fixture
def mock_embedding():
    """Mock 百炼 Embedding，返回确定性向量，不调用真实 API"""
    mock = MagicMock()
    mock.model = "text-embedding-v2"
    mock.api_key = "sk-test-mock-key"

    def fake_embed_query(text: str) -> list:
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(hash_val >> i) % 100 / 100.0 for i in range(384)]

    mock.embed_query = fake_embed_query
    mock.embed_documents = lambda texts: [fake_embed_query(t) for t in texts]
    return mock


@pytest.fixture
def mock_llm():
    """Mock LLM，返回固定的流式 token 列表，不调用真实 API"""
    mock = MagicMock()
    # stream() 返回一个可迭代的 token 列表
    mock.stream.return_value = ["这是", "一个", "测试", "回答", "。"]
    return mock


@pytest.fixture
def sample_documents():
    """生成一些示例 LangChain Document，用于测试分割、检索等"""
    from langchain_core.documents import Document

    return [
        Document(
            page_content="iPhone 15 Pro Max 采用钛金属设计，搭载 A17 Pro 芯片，支持 USB-C 接口。售价 ¥9,999 起。",
            metadata={"filename": "apple_products.txt", "file_type": "txt"},
        ),
        Document(
            page_content="华为 Mate 60 Pro 支持卫星通话功能，搭载麒麟 9000S 芯片，配备昆仑玻璃。售价 ¥6,999 起。",
            metadata={"filename": "huawei_products.txt", "file_type": "txt"},
        ),
        Document(
            page_content="本店支持 7 天无理由退货，15 天内换货。退货商品需保持完好，附赠品需一并退回。退款将在 1-3 个工作日内到账。",
            metadata={"filename": "return_policy.txt", "file_type": "txt"},
        ),
        Document(
            page_content="小米 14 Ultra 搭载徕卡光学镜头，配备骁龙 8 Gen 3 处理器，支持 90W 快充。售价 ¥5,999 起。",
            metadata={"filename": "xiaomi_products.txt", "file_type": "txt"},
        ),
        Document(
            page_content="三星 Galaxy S24 Ultra 采用钛金属框架，内置 S Pen，支持 Galaxy AI 功能。售价 ¥9,699 起。",
            metadata={"filename": "samsung_products.txt", "file_type": "txt"},
        ),
    ]


# ======================== JWT Token 辅助函数 ========================

def make_auth_header(token: str) -> dict:
    """快捷生成 Bearer token 请求头"""
    return {"Authorization": f"Bearer {token}"}


# ======================== 测试数据工厂 ========================

@pytest.fixture
def knowledge_base_payload():
    """创建知识库的请求体"""
    return {
        "name": "测试知识库",
        "description": "用于单元测试的知识库",
    }


@pytest.fixture
async def test_kb(db_session, test_user):
    """在测试数据库中创建一个知识库"""
    from datetime import datetime
    from backend.models.knowledge_base import KnowledgeBase

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kb = KnowledgeBase(
        id="test-kb-id-001",
        name="测试知识库",
        description="用于单元测试",
        owner_id=test_user.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(kb)
    await db_session.flush()
    return kb


@pytest.fixture
async def test_conversation(db_session, test_user, test_kb):
    """在测试数据库中创建一个会话"""
    from datetime import datetime
    from backend.models.conversation import Conversation

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conv = Conversation(
        id="test-conv-id-001",
        user_id=test_user.id,
        title="测试会话",
        kb_id=test_kb.id,
        message_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(conv)
    await db_session.flush()
    return conv
