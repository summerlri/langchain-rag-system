"""
问答 API — SSE 流式响应

这是用户与 RAG 系统交互的核心入口，实现了三个功能:
  1. send_message   — 发送问题，SSE 流式返回 AI 回答(打字机效果)
  2. get_messages   — 分页拉取历史消息记录
  3. regenerate     — 重新生成最后一条回答(用户不满意时点"重新回答")

为什么用 SSE (Server-Sent Events) 而不是 WebSocket?
  - SSE 是 HTTP 原生的单向推送(服务器→客户端)，实现简单、自动重连
  - 这个场景只需要服务器推送回答给前端，不需要前端推送数据给服务器(那用 POST 就够了)
  - 比 WebSocket 更节省连接资源，Nginx/负载均衡器无需特殊配置

为什么 assistant 消息在 SSE 流结束后才保存到数据库?
  - 流式生成过程中 token 是逐片到达的，必须收集完才能写入一条完整的 Message 记录
  - 如果在流中每收到一个 token 就 UPDATE 一次，会产生大量无意义的数据库写操作
  - 所以采用"流中收集 → 流结束一次性写入"的策略
"""
import json
import time
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.models.user import User
from backend.models.conversation import Conversation, Message
from backend.models.knowledge_base import KnowledgeBase
from backend.core.deps import get_current_user
from backend.core.exceptions import NotFoundException, BadRequestException
from backend.schemas.conversation import ChatRequest, MessageResponse
from backend.rag.pipeline import RAGPipeline

router = APIRouter(prefix="/api/chat", tags=["问答"])


# ══════════════════════════════════════════════════════════════════════════════
# 辅助函数: 验证"会话是否属于当前用户" + 返回 Conversation 对象
# 这个模式在 send_message、get_messages、regenerate 中重复了 3 次
# TODO: 未来可抽取为 FastAPI 依赖注入 get_conversation()，减少重复、防止遗漏
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/{conversation_id}")
async def send_message(
    conversation_id: str,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    发送消息，SSE 流式返回 AI 回答。

    整体流程:
      ① 校验会话归属(防止越权访问他人会话)
      ② 确定目标知识库(优先用请求指定的，否则用会话绑定的，都没有则取第一个可用)
      ③ 保存用户消息到数据库
      ④ 调用 RAGPipeline 流式问答
      ⑤ 在 SSE 流中推送 sources → token → done 事件
      ⑥ 流结束后保存完整的 assistant 消息到数据库

    为什么 assistant 消息不在 send_message 的 db session 中保存?
      - SSE 流是一个长时间运行的生成器，可能在数秒后才结束
      - 如果一直持有 send_message 的 db session，会锁住连接池，影响其他请求
      - 所以 assistant 消息在流内部使用独立的 async_session 保存，互不干扰
    """
    # ---- ① 验证会话归属 ----
    # 必须在 where 条件中同时匹配 conversation_id 和 user_id
    # 如果只匹配 conversation_id，用户可以遍历 ID 查看其他人的对话
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundException("会话不存在")

    # ---- ② 确定目标知识库 ----
    # 优先级: 请求参数 > 会话绑定 > 系统第一个可用
    kb_id = req.kb_id or conv.kb_id
    if not kb_id:
        kb_result = await db.execute(select(KnowledgeBase).limit(1))
        kb = kb_result.scalar_one_or_none()
        if not kb:
            raise BadRequestException("系统中还没有知识库，请联系管理员上传文档")
        kb_id = kb.id

    # 当前消息入库前读取最近 8 条历史，让“它、上一款”等追问能够被正确理解。
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(8)
    )
    history = [
        {"role": item.role, "content": item.content}
        for item in reversed(history_result.scalars().all())
    ]

    # ---- ③ 保存用户消息 ----
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=req.message,
        created_at=now,
    )
    db.add(user_msg)

    # ---- ④ 更新会话元信息 ----
    conv.message_count = (conv.message_count or 0) + 1
    conv.updated_at = now
    # 第一条消息时自动用用户问题作为会话标题(截取前30个字符，超长加省略号)
    # 为什么是 30? 因为前端会话列表宽度大约能显示 15 个中文字符，30 个半角字符刚好一行
    if conv.title == "新对话":
        conv.title = req.message[:30] + ("..." if len(req.message) > 30 else "")
    # StreamingResponse 会在当前接口逻辑返回后继续生成内容，而助手消息由新的
    # AsyncSession 保存。这里必须先提交用户消息并释放 SQLite 写锁，否则流结束时
    # 第二个会话写入助手消息会触发 "database is locked"。
    await db.commit()

    pipeline = RAGPipeline()

    # ---- ⑤ SSE 事件生成器 ----
    async def event_stream():
        """
        为什么 event_stream 是 async 内部函数?
          - StreamingResponse 需要一个异步生成器作为数据源
          - 用内部函数可以捕获外层变量(conversation_id, req, kb_id 等)，不用传参
          - nonlocal 允许修改外层的 collected_content、sources_data

        SSE 协议的格式要求: 每行以 "data: " 开头，以 "\n\n" 结尾
        前端 EventSource API 会自动根据这个格式解析事件
        """
        collected_content = ""  # 收集所有 token 片段，流结束后写入完整消息
        sources_data = []       # 检索到的参考来源数据
        token_count = 0
        latency_ms = 0

        try:
            async for event in pipeline.query(kb_id=kb_id, question=req.message, history=history):
                if event["type"] == "rewrite":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif event["type"] == "sources":
                    sources_data = event["data"]
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources_data}, ensure_ascii=False)}\n\n"

                elif event["type"] == "token":
                    collected_content += event["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': event['content']}, ensure_ascii=False)}\n\n"

                elif event["type"] == "done":
                    token_count = event["metadata"]["total_tokens"]
                    latency_ms = event["metadata"]["latency_ms"]

                    # ---- ⑥ 保存 assistant 消息 ----
                    # 为什么在这里 import async_session 而不是文件顶部?
                    #   - async_session 是 backend.db.database 模块的全局单例，外部直接引用会触发循环导入
                    #   - (RAGPipeline → pipeline.py → database.py，而 database.py 被多处引用)
                    #   - 延迟 import 是 Python 中解决循环依赖的常见做法
                    from backend.db.database import async_session
                    async with async_session() as session:
                        assistant_msg = Message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=collected_content,
                            sources=json.dumps(sources_data, ensure_ascii=False),
                            token_count=token_count,
                            latency_ms=latency_ms,
                            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        )
                        session.add(assistant_msg)
                        # 为什么又更新一次 message_count?
                        #   send_message 外层已经 +1(用户消息)，这里再 +1(assistant消息)
                        #   保证 message_count 始终反映真实的消息总数(用户+AI 各算一条)
                        result = await session.execute(
                            select(Conversation).where(Conversation.id == conversation_id)
                        )
                        c = result.scalar_one_or_none()
                        if c:
                            c.message_count = (c.message_count or 0) + 1
                            c.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        await session.commit()

                    yield f"data: {json.dumps({'type': 'done', 'metadata': event['metadata']}, ensure_ascii=False)}\n\n"

        except Exception as e:
            # 即使 LLM 生成中途失败，也要推送一个 error 事件给前端
            # 这样前端可以显示"生成失败，请重试"，而不是永远等待
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    # ---- 返回 SSE 流式响应 ----
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # 禁止缓存: 每次请求都要重新生成，不能让浏览器/CDN 缓存回答
            "Cache-Control": "no-cache",
            # 关闭 Nginx 的代理缓冲: 否则 Nginx 会等全部数据生成完才一次性发给客户端，失去流式意义
            "X-Accel-Buffering": "no",
            # 长连接: SSE 依赖持久连接，keep-alive 防止中间代理断开
            "Connection": "keep-alive",
        },
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    分页获取历史消息，按时间正序排列(旧→新)。

    为什么需要分页?
      - 长对话可能有几百条消息，一次性全部返回会撑爆内存和网络带宽
      - 20 条/页: 前端聊天界面一屏大约显示 10-15 条消息，20 条够 2 屏，用户滚动时加载下一页
      - 上限 100: 防止恶意请求一次性拉取海量数据
    """
    # ---- 校验会话归属(防止越权) ----
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundException("会话不存在")

    # 计算偏移量: 第 1 页 = offset 0, 第 2 页 = offset 20, ...
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        # 按时间正序: 用户先看到最早的对话，往下滚动是更新的
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            sources=m.sources,
            token_count=m.token_count,
            latency_ms=m.latency_ms,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/{conversation_id}/regenerate")
async def regenerate(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    重新生成最后一条回答。

    为什么叫"重新生成"而不是"重新回答"?
      - 用户看到不满意的回答 → 点击"重新生成"按钮 → 删掉最后一条 AI 回答 → 返回原始问题
      - 前端拿到原始问题后，自动调用 send_message 重新发送，触发新的 RAG 回答生成
      - 这样做的好处: 复用 send_message 的完整逻辑(检索+生成+保存)，不重复实现

    流程: 验证会话 → 找到最后一条 user 消息 → 删除最后一条 assistant 消息 → 返回原问题
    """
    # ---- 验证会话归属 ----
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundException("会话不存在")

    # ---- 找到最后一条用户消息(作为重新提问的内容) ----
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role == "user")
        .order_by(Message.created_at.desc())  # 降序取最新
        .limit(1)
    )
    last_user_msg = result.scalar_one_or_none()
    if not last_user_msg:
        raise BadRequestException("没有可重新生成的消息")

    # ---- 删除最后一条 assistant 消息(为新生回答腾位置) ----
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    last_ai_msg = result.scalar_one_or_none()
    if last_ai_msg:
        await db.delete(last_ai_msg)
        await db.flush()

    # 只返回原始问题，不在这里重新调用 RAGPipeline
    # 因为 RAGPipeline.query() 返回的是 SSE 流，不适合在普通 JSON 响应中返回
    # 前端拿到 question 后会自动用 send_message 重新发起 SSE 请求
    return {"message": "请重新发送消息", "question": last_user_msg.content}
