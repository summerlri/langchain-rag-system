"""
单元测试 — Pydantic 请求/响应模型 (backend/schemas/)
"""
import pytest
from pydantic import ValidationError
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    ChangePasswordRequest,
    TokenResponse,
)
from backend.schemas.knowledge_base import (
    KBCreateRequest,
    KBUpdateRequest,
)
from backend.schemas.conversation import (
    ChatRequest,
    ConversationCreateRequest,
)


class TestRegisterRequest:
    """注册请求校验"""

    def test_valid_register(self):
        req = RegisterRequest(username="newuser", password="pass123456", email="a@b.com")
        assert req.username == "newuser"

    def test_username_too_short(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="x", password="pass123456")

    def test_username_too_long(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="x" * 51, password="pass123456")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="validuser", password="12345")

    def test_email_default_empty(self):
        req = RegisterRequest(username="validuser", password="pass123456")
        assert req.email == ""


class TestLoginRequest:
    """登录请求校验"""

    def test_valid_login(self):
        req = LoginRequest(username="admin", password="123456789")
        assert req.username == "admin"

    def test_missing_password(self):
        with pytest.raises(ValidationError):
            LoginRequest(username="admin")


class TestChangePasswordRequest:
    """修改密码请求校验"""

    def test_valid_change(self):
        req = ChangePasswordRequest(old_password="old123456", new_password="new123456")
        assert req.new_password == "new123456"

    def test_new_password_too_short(self):
        with pytest.raises(ValidationError):
            ChangePasswordRequest(old_password="old123456", new_password="12345")


class TestTokenResponse:
    """Token 响应模型"""

    def test_default_token_type(self):
        resp = TokenResponse(
            access_token="xxx.yyy.zzz",
            username="alice",
            is_admin=False,
        )
        assert resp.token_type == "bearer"


class TestKnowledgeBaseSchemas:
    """知识库请求模型"""

    def test_create_valid(self):
        req = KBCreateRequest(name="我的知识库", description="测试用")
        assert req.name == "我的知识库"

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            KBCreateRequest(name="x" * 101, description="测试")

    def test_update_partial(self):
        req = KBUpdateRequest(name="新名称")  # description 可选
        assert req.name == "新名称"
        assert req.description is None


class TestChatSchemas:
    """聊天请求模型"""

    def test_chat_request_minimal(self):
        req = ChatRequest(message="你好")
        assert req.message == "你好"
        assert req.kb_id is None

    def test_chat_request_with_kb(self):
        req = ChatRequest(message="iPhone 价格？", kb_id="kb-001")
        assert req.kb_id == "kb-001"

    def test_conversation_create(self):
        req = ConversationCreateRequest(kb_id="kb-001", title="新对话")
        assert req.title == "新对话"
