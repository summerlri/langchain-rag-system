"""
会话管理 API
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.core.deps import get_current_user
from backend.core.exceptions import NotFoundException
from backend.schemas.conversation import (
    ConversationCreateRequest, ConversationUpdateRequest, ConversationResponse,
)

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有会话，按更新时间倒序"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()

    return [
        ConversationResponse(
            id=c.id,
            user_id=c.user_id,
            title=c.title,
            kb_id=c.kb_id,
            message_count=c.message_count or 0,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    req: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """新建会话"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conv = Conversation(
        user_id=current_user.id,
        title=req.title,
        kb_id=req.kb_id,
        message_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.flush()

    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        kb_id=conv.kb_id,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    req: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新会话标题"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundException("会话不存在")

    conv.title = req.title
    conv.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db.flush()

    return ConversationResponse(
        id=conv.id, user_id=conv.user_id, title=conv.title,
        kb_id=conv.kb_id, message_count=conv.message_count or 0,
        created_at=conv.created_at, updated_at=conv.updated_at,
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话（级联删除所有消息）"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundException("会话不存在")

    await db.delete(conv)
    await db.flush()
    return {"message": "会话已删除"}
