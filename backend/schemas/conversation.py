"""
会话和消息相关 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="新对话", max_length=200)
    kb_id: Optional[str] = Field(default=None)


class ConversationUpdateRequest(BaseModel):
    title: str = Field(..., max_length=200)


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    kb_id: str | None = None
    message_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: str | None = None  # JSON 字符串
    token_count: int | None = None
    latency_ms: int | None = None
    created_at: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户问题")
    kb_id: Optional[str] = Field(default=None, description="指定知识库ID（可选）")
