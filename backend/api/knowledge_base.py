"""
知识库管理 API — 仅管理员可访问
"""
import os
import uuid
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.models.user import User
from backend.models.knowledge_base import KnowledgeBase, Document
from backend.core.deps import get_current_admin
from backend.core.exceptions import NotFoundException, BadRequestException
from backend.schemas.knowledge_base import (
    KBCreateRequest, KBUpdateRequest, KBResponse, DocumentResponse,
)
from backend.rag.pipeline import RAGPipeline
from backend.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库管理"])

# 创建上传目录
os.makedirs(settings.upload_dir, exist_ok=True)


# ==================== 知识库 CRUD ====================

@router.get("", response_model=list[KBResponse])
async def list_kbs(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """获取所有知识库列表"""
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))
    kbs = result.scalars().all()

    resp = []
    for kb in kbs:
        # 统计文档数量
        count_result = await db.execute(
            select(func.count(Document.id)).where(Document.kb_id == kb.id)
        )
        doc_count = count_result.scalar() or 0
        resp.append(KBResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description or "",
            owner_id=kb.owner_id,
            doc_count=doc_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        ))
    return resp


@router.post("", response_model=KBResponse)
async def create_kb(
    req: KBCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """创建知识库"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kb = KnowledgeBase(
        name=req.name,
        description=req.description,
        owner_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(kb)
    await db.flush()

    return KBResponse(
        id=kb.id, name=kb.name, description=kb.description or "",
        owner_id=kb.owner_id, doc_count=0,
        created_at=kb.created_at, updated_at=kb.updated_at,
    )


@router.put("/{kb_id}", response_model=KBResponse)
async def update_kb(
    kb_id: str, req: KBUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """更新知识库信息"""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundException("知识库不存在")

    if req.name is not None:
        kb.name = req.name
    if req.description is not None:
        kb.description = req.description
    kb.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db.flush()

    count_result = await db.execute(select(func.count(Document.id)).where(Document.kb_id == kb.id))
    doc_count = count_result.scalar() or 0

    return KBResponse(
        id=kb.id, name=kb.name, description=kb.description or "",
        owner_id=kb.owner_id, doc_count=doc_count,
        created_at=kb.created_at, updated_at=kb.updated_at,
    )


@router.delete("/{kb_id}")
async def delete_kb(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """删除知识库（含文档和向量数据）"""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundException("知识库不存在")

    # 删除向量数据
    from backend.rag.pipeline import get_vs_manager
    vs = get_vs_manager()
    await asyncio.to_thread(vs.delete_collection, kb_id)

    # 删除数据库记录（CASCADE 会删除关联文档记录）
    await db.delete(kb)
    await db.flush()

    return {"message": "知识库已删除"}


# ==================== 文档管理 ====================

@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """获取知识库中的文档列表"""
    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id).order_by(Document.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return [DocumentResponse(
        id=doc.id, kb_id=doc.kb_id, filename=doc.filename,
        file_type=doc.file_type or "", file_size=doc.file_size or 0,
        status=doc.status, chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        uploaded_at=doc.uploaded_at, processed_at=doc.processed_at,
    ) for doc in docs]


@router.post("/{kb_id}/documents", response_model=DocumentResponse)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """上传文档并触发异步处理"""
    # 检查知识库是否存在
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundException("知识库不存在")

    # 校验文件类型
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_file_types:
        raise BadRequestException(f"不支持的文件类型: .{ext}，支持: {settings.allowed_file_types}")

    # 存储文件
    doc_id = str(uuid.uuid4())
    safe_filename = f"{doc_id}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, safe_filename)

    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise BadRequestException(f"文件大小超过限制 ({settings.max_upload_size_mb}MB)")

    with open(file_path, "wb") as f:
        f.write(content)

    # 创建数据库记录
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = Document(
        id=doc_id,
        kb_id=kb_id,
        filename=file.filename,
        file_type=ext,
        file_size=len(content),
        file_path=file_path,
        status="processing",
        uploaded_at=now,
    )
    db.add(doc)
    await db.flush()

    # 异步后台处理
    pipeline = RAGPipeline()
    async def process():
        result = await pipeline.ingest_document(file_path, file.filename, kb_id, doc_id)
        from backend.db.database import async_session
        async with async_session() as session:
            result2 = await session.execute(select(Document).where(Document.id == doc_id))
            doc_record = result2.scalar_one_or_none()
            if doc_record:
                doc_record.status = result["status"]
                doc_record.chunk_count = result.get("chunk_count", 0)
                doc_record.error_message = result.get("error_message")
                doc_record.processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await session.commit()

    background_tasks.add_task(process)

    return DocumentResponse(
        id=doc.id, kb_id=doc.kb_id, filename=doc.filename,
        file_type=doc.file_type or "", file_size=doc.file_size or 0,
        status=doc.status, chunk_count=0,
        error_message=None,
        uploaded_at=doc.uploaded_at, processed_at=None,
    )


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str, doc_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """删除文档（含文件+向量数据）"""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundException("文档不存在")

    # 删除向量数据
    from backend.rag.pipeline import get_vs_manager
    vs = get_vs_manager()
    await asyncio.to_thread(vs.delete_by_doc_id, kb_id, doc_id)

    # 删除文件
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # 删除记录
    await db.delete(doc)
    await db.flush()

    return {"message": "文档已删除"}


@router.post("/{kb_id}/documents/{doc_id}/reprocess")
async def reprocess_document(
    kb_id: str, doc_id: str,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """重新处理文档"""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundException("文档不存在")
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise BadRequestException("原始文件不存在")

    # 删除旧向量
    from backend.rag.pipeline import get_vs_manager
    vs = get_vs_manager()
    await asyncio.to_thread(vs.delete_by_doc_id, kb_id, doc_id)

    # 更新状态
    doc.status = "processing"
    doc.error_message = None
    await db.flush()

    # 重新处理
    pipeline = RAGPipeline()
    async def process():
        result = await pipeline.ingest_document(doc.file_path, doc.filename, kb_id, doc_id)
        from backend.db.database import async_session
        async with async_session() as session:
            result2 = await session.execute(select(Document).where(Document.id == doc_id))
            doc_record = result2.scalar_one_or_none()
            if doc_record:
                doc_record.status = result["status"]
                doc_record.chunk_count = result.get("chunk_count", 0)
                doc_record.error_message = result.get("error_message")
                doc_record.processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await session.commit()

    background_tasks.add_task(process)

    return {"message": "文档已提交重新处理"}
