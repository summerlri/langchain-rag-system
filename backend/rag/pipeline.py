"""
RAG 主流水线 — 文档入库 + 问答检索生成

这是整个 RAG 系统的核心编排层，负责把 loader → splitter → embedding → vector_store → retriever → LLM
这些独立组件串联成两条完整的业务链路：

  文档入库链路:  文件 → 加载 → 分割(500字/块,50字重叠) → 向量化 → 存入 ChromaDB
  问答生成链路:  问题 → 缓存查询 → MMR检索(top_k=4) → 拼接上下文 → LLM流式生成 → SSE推送给前端

设计原则:
  - 所有阻塞操作(磁盘IO/API调用)都通过 asyncio.to_thread 丢到线程池，避免阻塞事件循环
  - 检索结果用两级缓存(cache_manager)，减少重复查询的 Embedding 调用，节省 API 费用
  - SSE 事件流(sources → token → done)让前端可以逐字渲染，避免用户长时间等待白屏
"""
import os
import uuid
import time
import json
import asyncio
from typing import List, AsyncIterator, Optional
from datetime import datetime
from langchain_core.documents import Document

from backend.config import get_settings
from backend.rag.loader import DocumentLoader
from backend.rag.splitter import split_documents
from backend.rag.embedding import BailianEmbeddings
from backend.rag.vector_store import VectorStoreManager
from backend.rag.retriever import RAGRetriever
from backend.rag.chain import get_llm, format_docs, RAG_SYSTEM_PROMPT
from backend.cache.cache_manager import cache_manager

settings = get_settings()

# ══════════════════════════════════════════════════════════════════
# 全局单例 (Global Singletons)
# ══════════════════════════════════════════════════════════════════
# 为什么用模块级全局变量而不是 FastAPI app.state?
#   - 这些组件是无状态的(Embedding/LLM 每次请求独立调用)，不需要请求级别的隔离
#   - 复用实例可以共享底层连接池(HTTP session、ChromaDB client)，避免每次请求都重新建立连接
#   - 坏处: 多 worker 模式下每个进程各有一份，需要在 uvicorn 配置中控制 worker 数量
#   - 如果以后需要更好的多进程隔离，可以把这些单例挪到 FastAPI app.state 中管理

# Embedding 单例: 共享 HTTP 连接池，避免每次请求都重新创建 dashscope 客户端
_embedding = None

# VectorStoreManager 单例: 共享 ChromaDB PersistentClient，避免重复打开数据库文件
_vs_manager = None

# RAGRetriever 单例: 依赖 vs_manager，同样复用
_retriever = None

# LLM 单例: 共享百炼 Tongyi 的连接，避免每次流式生成都重建客户端
_llm = None


def get_embedding() -> BailianEmbeddings:
    """
    懒加载获取 Embedding 单例。

    为什么用懒加载(首次调用时才创建)而不是模块导入时创建?
      - 模块导入时 .env 可能还没加载完成，环境变量可能为空
      - 懒加载确保 config 已经被正确初始化后再创建实例
    """
    global _embedding
    if _embedding is None:
        _embedding = BailianEmbeddings()
    return _embedding


def get_vs_manager() -> VectorStoreManager:
    """懒加载获取向量存储管理器单例"""
    global _vs_manager
    if _vs_manager is None:
        _vs_manager = VectorStoreManager(embedding=get_embedding())
    return _vs_manager


def get_retriever() -> RAGRetriever:
    """懒加载获取检索器单例"""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever(vector_store_manager=get_vs_manager())
    return _retriever


def get_llm_instance():
    """
    懒加载获取 LLM 单例。

    注意: 每次 query() 都会调用一次 get_llm_instance()，但因为已经初始化过，
    不会重复创建，只是返回已有实例的引用。
    """
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


class RAGPipeline:
    """
    RAG 完整流水线 — 封装文档入库和问答检索生成两条核心链路。

    设计思路: 把 RAG 的各个步骤(加载→分割→向量化→存储 / 检索→拼接→生成)
    编排成高层方法，让 API 层(chat.py / knowledge_base.py)只需要调用一个方法
    就能完成整个流程，不需要了解底层细节。
    """

    def __init__(self):
        """初始化时注入三个核心组件的单例引用"""
        self.embedding = get_embedding()
        self.vs_manager = get_vs_manager()
        self.retriever = get_retriever()

    # ==================== 文档入库 ====================

    async def ingest_document(self, file_path: str, filename: str, kb_id: str, doc_id: str) -> dict:
        """
        执行文档入库流水线：加载 → 分割 → 向量化 → 写入 ChromaDB。

        参数:
          file_path: 上传文件在磁盘上的路径(如 data/uploads/abc123_report.pdf)
          filename:  用户上传时的原始文件名(用于元数据记录)
          kb_id:     目标知识库 ID(每个知识库在 ChromaDB 中对应一个独立 collection)
          doc_id:    数据库中的文档记录 ID(用于生成 chunk 的唯一标识)

        返回:
          {"status": "completed", "chunk_count": N}  成功
          {"status": "failed",    "error_message": ""} 失败

        性能考虑:
          - 加载、分割、向量化都是 CPU/IO 密集操作，用 asyncio.to_thread 丢到线程池
            执行，避免阻塞 FastAPI 的事件循环。这是 asyncio + 同步库的常见配合模式。
          - 为什么不在 async def 中直接 await 这些操作? 因为 LangChain 的 Loader/Splitter
            都是同步代码，没有提供 async 版本。asyncio.to_thread 是最简单的桥接方式。

        为什么这个函数在 BackgroundTasks 中调用?
          - 文档入库可能需要几秒到几十秒(取决于文件大小和 API 响应速度)
          - HTTP 请求不能等这么久，所以 API 接口先返回"处理中"，后台任务慢慢做
        """
        try:
            # 1. 加载文档 — 根据文件类型自动选择 loader(PDF/DOCX/TXT/CSV/XLSX/MD)
            docs = await asyncio.to_thread(DocumentLoader.load, file_path)

            # 2. 分割文档 — 每块 500 字符、重叠 50 字符
            #    为什么是 500+50? 这是电商场景下的经验值:
            #      500 字符 ≈ 中文 250 字，刚好够描述一个商品的完整属性(名称+价格+参数)
            #      50 字符重叠 ≈ 中文 25 字，确保跨块边界的信息不会丢失(如商品名称在块尾、价格在下一块头)
            chunks = await asyncio.to_thread(split_documents, docs, chunk_size=500, chunk_overlap=50)

            # 3. 给每个 chunk 打上溯源标记 — 这样检索结果可以追溯到原始文档，前端可以展示"参考来源"
            for chunk in chunks:
                chunk.metadata["doc_id"] = doc_id
                chunk.metadata["kb_id"] = kb_id

            # 4. 写入向量数据库 — 生成唯一 ID 格式: {doc_id}_chunk_{序号}
            #    用 doc_id 做前缀是为了方便按文档删除: delete_collection 时直接搜 doc_id 前缀
            chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
            await asyncio.to_thread(
                self.vs_manager.add_documents,
                kb_id=kb_id,
                documents=chunks,
                metadatas=[c.metadata for c in chunks],
                ids=chunk_ids,
            )

            return {"status": "completed", "chunk_count": len(chunks)}

        except Exception as e:
            # 注意: 这里兜住所有异常是为了保证后台任务不会静默崩溃导致文档状态永远停留在 processing
            # 错误信息会被写入数据库的 error_message 字段，管理员可以看到具体原因
            return {"status": "failed", "error_message": str(e)}

    # ==================== 问答检索生成 ====================

    def _do_retrieve(self, kb_id: str, query: str) -> List[dict]:
        """
        执行一次检索操作(同步方法，计划在线程池中执行)。

        为什么 top_k=4?
          - RAG 中太少(1-2)可能漏掉相关信息，太多(8-10)会塞入过多噪音
          - 4 是电商场景的平衡点: 一个商品查询通常 1-2 个 chunk 就有答案，
            额外 2 个提供备选和对比信息，既充分又不让 LLM 上下文超长
        """
        return self.retriever.retrieve_with_scores(kb_id, query, top_k=4)

    async def query(self, kb_id: str, question: str) -> AsyncIterator[dict]:
        """
        执行 RAG 问答流水线，以 SSE (Server-Sent Events) 事件流的方式返回结果。

        为什么用 SSE 而不是普通 JSON 响应?
          - LLM 生成一段完整回答通常需要 2-10 秒，如果等全部生成完再返回，用户盯着空白页面
          - SSE 让前端可以逐字渲染(类似 ChatGPT 的打字效果)，用户体验更好
          - SSE 是 HTTP 原生支持的单向流，比 WebSocket 轻量，适合这个场景

        SSE 事件格式:
          {"type": "sources", "data": [...]}   → 检索到的参考文档(前端展示"参考资料")
          {"type": "token",   "content": "..."} → 逐个 token 推送(前端逐字拼接)
          {"type": "done",    "metadata": {...}} → 流结束(前端显示总 token 和耗时)

        参数:
          kb_id:    知识库 ID，决定从哪个 collection 中检索
          question: 用户输入的原始问题

        每调用一次 query() 会:
          1. 查缓存 → 命中则跳过 Embedding 调用(省钱)
          2. 检索 ChromaDB → 拿到 top-4 相关 chunk
          3. 拼接成 Prompt → 发给 LLM 流式生成
          4. 逐 token 推送回前端
        """
        start_time = time.time()

        # Step 1: 检索（带缓存）
        # 为什么缓存检索结果?
        #   - 相同问题重复检索会再次调用 Embedding API(百炼 text-embedding-v2 按 token 计费)
        #   - 电商场景下用户的常见问题(如"iPhone多少钱")会被反复问到
        #   - 缓存 30 分钟(1800s): 既覆盖了大部分重复查询窗口，又不会让结果太陈旧
        cache_key = f"query:{kb_id}:{hash(question)}"
        sources = cache_manager.get(cache_key)
        if sources is None:
            sources = await asyncio.to_thread(self._do_retrieve, kb_id, question)
            if sources:
                cache_manager.set(cache_key, sources, ttl=1800)

        # Step 2: 推送检索结果给前端(前端据此展示"参考来源"面板)
        yield {"type": "sources", "data": sources}

        # 无结果时 — 友好提示而非报错，让用户知道是知识库的问题而不是系统坏了
        if not sources:
            yield {
                "type": "token",
                "content": "抱歉，知识库中暂未收录相关信息，请尝试其他问题或联系管理员更新知识库。"
            }
            yield {"type": "done", "metadata": {"total_tokens": 0, "latency_ms": int((time.time() - start_time) * 1000)}}
            return

        # Step 3: 把检索到的 chunk 组装成 LLM 能理解的"上下文文档"
        # 每个 chunk 还带有来源文件名和编号，LLM 在回答中可以引用 "[1] 来源: xxx.pdf"
        docs_for_context = []
        for s in sources:
            doc = Document(
                page_content=s["content"],
                metadata={"filename": s["filename"], "doc_id": s["doc_id"], "chunk_index": s["chunk_index"]}
            )
            docs_for_context.append(doc)
        context = format_docs(docs_for_context)

        # Step 4: 流式生成 — 把拼接好的 Prompt 发给百炼 Qwen 模型
        llm = get_llm_instance()
        prompt_text = RAG_SYSTEM_PROMPT.format(context=context, question=question)
        total_tokens = 0

        try:
            # llm.stream() 返回一个同步迭代器，每次 yield 一个 token 片段
            # 这里直接在 async 函数中迭代同步迭代器是安全的，因为 yield 本身不会阻塞事件循环
            for chunk in llm.stream(prompt_text):
                total_tokens += len(chunk)
                yield {"type": "token", "content": chunk}
        except Exception as e:
            # LLM 生成失败时，把错误信息也作为 token 推送，保证前端总能看到一个响应
            # 而不是整个 SSE 流中断(那会让前端陷入无限等待)
            yield {"type": "token", "content": f"\n\n[生成失败: {str(e)}]"}

        # Step 5: 发送结束信号 — 前端可以根据 metadata 展示"生成耗时 3.2 秒，消耗 450 tokens"
        latency_ms = int((time.time() - start_time) * 1000)
        yield {"type": "done", "metadata": {"total_tokens": total_tokens, "latency_ms": latency_ms}}
