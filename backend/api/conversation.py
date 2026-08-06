"""
会话管理 API
"""
import json
import re
import logging
from urllib.parse import quote
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from backend.db.database import get_db
from backend.models.user import User
from backend.models.conversation import Conversation, Message
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


def _format_message_as_markdown(msg) -> list[str]:
    """将单条消息格式化为 Markdown 行列表"""
    lines = []
    role_label = "👤 用户" if msg.role == "user" else "🤖 AI 助手"
    lines.append(f"## {role_label}")
    lines.append("")
    lines.append(msg.content)
    lines.append("")

    # AI 回答附带引用来源
    if msg.role == "assistant" and msg.sources:
        try:
            sources = json.loads(msg.sources)
            if sources:
                lines.append("> 📚 **参考来源**:")
                for i, src in enumerate(sources, 1):
                    filename = src.get("filename", "未知文件")
                    score = src.get("score", 0)
                    lines.append(f"> [{i}] {filename}（匹配度: {score * 100:.1f}%）")
                lines.append("")
        except (json.JSONDecodeError, TypeError):
            logger.warning("导出对话时解析 sources JSON 失败: %s", msg.id)

    # Token 和延迟统计（用 is not None 避免 0 值被误判为空）
    info_parts = []
    if msg.token_count is not None:
        info_parts.append(f"Token: {msg.token_count}")
    if msg.latency_ms is not None:
        info_parts.append(f"耗时: {msg.latency_ms}ms")
    if info_parts:
        lines.append(f"*{' | '.join(info_parts)}*")
        lines.append("")

    lines.append("---")
    lines.append("")
    return lines


@router.get("/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出对话为 Markdown 文件"""
    # 查询会话 + 关联消息（用 selectinload 避免 N+1 查询）
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundException("会话不存在")

    # 构建 Markdown 内容
    lines = [
        f"# {conv.title}",
        "",
        f"- **会话 ID**: {conv.id}",
        f"- **创建时间**: {conv.created_at}",
        f"- **更新时间**: {conv.updated_at}",
        f"- **消息数量**: {len(conv.messages)} 条",
        "",
        "---",
        "",
    ]

    for msg in conv.messages:
        lines.extend(_format_message_as_markdown(msg))

    md_content = "\n".join(lines)

    # 文件名清理：替换 Windows 和 Markdown 中不允许的字符
    safe_title = re.sub(r'[<>:"/\\|?*#]', '_', conv.title)
    safe_title = safe_title.replace(" ", "_").strip("._")[:50]
    filename = f"{safe_title}_{conv.id[:8]}.md"

    # 用 RFC 5987 编码处理中文等非 ASCII 字符，兼容所有浏览器
    encoded_filename = quote(filename, safe="")
    content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

    return Response(
        content=md_content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": content_disposition},
    )
