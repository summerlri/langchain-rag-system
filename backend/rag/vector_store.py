"""
ChromaDB 向量存储封装

ChromaDB 是一个开源的向量数据库，专门为大模型应用设计:
  - 持久化存储在磁盘(非内存)，服务重启数据不丢失
  - 内建了 HNSW 近似最近邻算法，查询速度快(O(log n))
  - 支持元数据过滤(按 doc_id、kb_id 等字段筛选)

为什么选 ChromaDB 而不是 Pinecone / Weaviate / Milvus?
  ChromaDB 的优势是零配置开箱即用、嵌入式部署(不需要额外服务进程)，
  非常适合中小规模 RAG 项目(<100万文档)。如果需要横向扩展，可以迁移到 Milvus。

存储架构:
  每个知识库(kb_xxx)对应 ChromaDB 中的一个独立 collection。
  好处: 知识库之间的向量完全隔离，删除知识库只需删 collection，互不影响。
"""
import os
from typing import List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from backend.config import get_settings
from backend.rag.embedding import BailianEmbeddings

settings = get_settings()


class VectorStoreManager:
    """
    ChromaDB 向量存储管理器 — 封装 collection 的创建、读写、删除操作。

    使用模式: 每个实例持有一个 PersistentClient，通过 get_store(kb_id)
    获取具体知识库的向量存储。不同知识库的数据在 ChromaDB 层面完全隔离。

    生命周期: Pipeline 级别的单例(在 pipeline.py 中通过 get_vs_manager() 懒加载)。
    关闭时客户端自动释放文件句柄。
    """

    def __init__(self, embedding: BailianEmbeddings = None):
        """
        初始化 ChromaDB 持久化客户端。

        参数:
          embedding: 嵌入模型实例(默认 BailianEmbeddings)。
                     ChromaDB 在写入和查询时自动调用 embedding 生成向量，
                     所以 VectorStoreManager 本身不需要知道向量的维度或算法细节。
        """
        # 确保存储目录存在 — ChromaDB 不会自动创建目录
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)

        self._embedding = embedding or BailianEmbeddings()
        # anonymized_telemetry=False 关闭 ChromaDB 的后台统计数据上报
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def get_collection_name(self, kb_id: str) -> str:
        """
        生成 ChromaDB collection 名称: kb_{知识库ID}

        为什么在 kb_id 前加 kb_ 前缀?
          ChromaDB collection 名称是全局命名空间，加前缀可以:
          ① 避免与系统内部 collection 冲突
          ② 一眼识别哪些 collection 是知识库(调试友好)
        """
        return f"kb_{kb_id}"

    def get_store(self, kb_id: str) -> Chroma:
        """
        获取或创建指定知识库的 Chroma 向量存储。

        Chroma 类(来自 langchain_chroma)自动处理"不存在则创建"的逻辑:
          - collection 不存在 → 创建新的，绑定指定的 embedding_function
          - collection 已存在 → 直接复用，不会重建(数据安全)
        """
        collection_name = self.get_collection_name(kb_id)
        return Chroma(
            client=self._client,
            collection_name=collection_name,
            embedding_function=self._embedding,
        )

    def add_documents(self, kb_id: str, documents: list, metadatas: Optional[list] = None,
                      ids: Optional[list] = None) -> None:
        """
        向知识库批量添加文档向量。

        流程: get_store 获取 collection → store.add_documents 调用 embedding → 写入磁盘

        为什么 metadatas 参数标注 Optional 但不使用?
          在 History 中注释解释了原因: LangChain Documents 自带 metadata 属性，
          如果同时传 metadatas 参数会导致参数冲突(Chroma 会尝试合并两份 metadata)。
          保留参数是为了保持接口兼容性，实际传入 None 即可。
        """
        store = self.get_store(kb_id)
        # LangChain Documents 已自带 metadata(field: Document.metadata)，直接用它即可
        store.add_documents(documents=documents, ids=ids)

    def search(self, kb_id: str, query: str, top_k: int = 10) -> list:
        """
        语义搜索 — MMR 混合检索。

        fetch_k=top_k*2: 候选池大小为最终返回数的 2 倍，这是 MMR 算法的经验最佳实践。
        候选池太小 → 多样性不够; 候选池太大 → 查询慢且收益递减。
        """
        store = self.get_store(kb_id)
        return store.max_marginal_relevance_search(query, k=top_k, fetch_k=top_k * 2)

    def delete_by_doc_id(self, kb_id: str, doc_id: str) -> None:
        """
        按文档 ID 删除该文档的所有向量块。

        步骤: ① 通过元数据过滤找到该文档的所有 chunk ID
              ② 批量删除
        ChromaDB 的 collection.get(where={"doc_id": doc_id}) 可以用元数据筛选，
        不需要遍历所有 chunk，效率很高。
        """
        store = self.get_store(kb_id)
        # 用 ChromaDB 的元数据过滤功能找到该文档的所有 chunk
        collection = self._client.get_collection(self.get_collection_name(kb_id))
        results = collection.get(where={"doc_id": doc_id})
        if results and results["ids"]:
            store.delete(ids=results["ids"])

    def delete_collection(self, kb_id: str) -> None:
        """
        删除整个知识库的向量集合。

        为什么 try/except?
          ChromaDB 在 collection 不存在时 delete_collection 会抛异常。
          这里只捕获并忽略，因为"要删除的东西已经不存在"对调用者来说不算错误。
          但是!! 这个 except 太宽泛(捕获了所有 Exception)，除了 NotFoundError 外，
          还可能会掩盖权限错误或磁盘满等真实故障 → 已在安全审计中标记，建议后续精细化。
        """
        collection_name = self.get_collection_name(kb_id)
        try:
            self._client.delete_collection(collection_name)
        except Exception:
            pass  # 集合不存在时忽略——但建议改为捕获特定异常类型
