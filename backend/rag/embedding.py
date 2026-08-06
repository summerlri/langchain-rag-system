"""
百炼 Embedding 封装 — 使用阿里云 DashScope API 生成文本向量

Embedding 是 RAG 系统的"理解"环节: 把人类可读的文本转成机器可比较的数字向量。
向量之间的距离(余弦相似度)代表了语义上的相似程度:
  - "iPhone 15 价格" 和 "iPhone 15 Pro 售价 ¥9,999" → 向量距离近(语义相似)
  - "iPhone 15 价格" 和 "退货政策 7天内可退" → 向量距离远(话题不同)

为什么每段文本都要做 Embedding?
  → 用户的自然语言问题("华为多少钱")和知识库中的正式描述("华为 Mate 60 Pro 售价 ¥6,999")
    字面上不完全匹配，但语义上高度相关。Embedding 可以跨越这种"表达差异"。

为什么结果要缓存?
  - 阿里云百炼 text-embedding-v2 按 token 计费: 输入 ¥0.0007/千tokens
  - 一个 500 字的中文 chunk ≈ 250 tokens，嵌入式维度 1536
  - 如果 100 个文档 × 50 chunks = 5000 次调用，缓存可以省大钱
  - 文本的嵌入向量是确定的(同样输入→同样输出)，天然适合缓存
  - TTL=30天: 文档如果不变更，嵌入结果永久有效；30天是保守的刷新周期
"""
from typing import List
from langchain_core.embeddings import Embeddings
from dashscope import TextEmbedding
from backend.config import get_settings
from backend.cache.cache_manager import cache_manager

settings = get_settings()


class BailianEmbeddings(Embeddings):
    """
    阿里云百炼 Embedding 模型封装，兼容 LangChain Embeddings 接口。

    实现了两个核心方法(这是 LangChain 要求的接口契约):
      embed_documents(texts) → List[List[float]]  批量嵌入(文档入库用)
      embed_query(text)      → List[float]         单条嵌入(用户查询用)

    为什么继承 LangChain 的 Embeddings 基类?
      → 让这个类可以被 LangChain Chroma 直接使用，自动在向量存储时调用 embed_documents，
         在检索时调用 embed_query，无需在外部手动转换。

    缓存架构: 两级(L1内存LRU + L2磁盘diskcache) → 命中时零 API 调用，零费用
    """

    def __init__(self, model: str = None, api_key: str = None):
        """
        参数:
          model:   百炼模型名(默认 text-embedding-v2，1536维输出)
          api_key: DashScope API Key(默认从环境变量 DASHSCOPE_API_KEY 读取)
        """
        self.model = model or settings.embedding_model
        self.api_key = api_key or settings.dashscope_api_key

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        批量调用百炼 API 生成向量。核心逻辑:

        ① 先查缓存 → ② 未命中的调用 API → ③ 写入缓存 → ④ 返回完整结果

        为什么逐条调用而不是批量(batch)?
          百炼 Embedding API 每次只支持输入一段文本(input 参数是 str 而非 List[str])。
          虽然逐条调用比批量慢，但配合缓存后，重复文本零 API 调用，实际效果很好。

        缓存 Key 设计:
          emb:{model}:{text} → 区分不同模型和文本，模型切换时缓存自动失效
        """
        # ① 先查缓存 —— 已嵌入过的文本直接拿结果，跳过 API 调用
        uncached_texts = []
        uncached_indices = []
        results = [None] * len(texts)

        for i, text in enumerate(texts):
            cache_key = f"emb:{self.model}:{text}"
            cached = cache_manager.get(cache_key)
            if cached is not None:
                results[i] = cached
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # ② 未命中缓存的调用百炼 API
        if uncached_texts:
            for idx, text in zip(uncached_indices, uncached_texts):
                resp = TextEmbedding.call(
                    model=self.model,
                    api_key=self.api_key,
                    input=text,
                )
                if resp.status_code == 200:
                    embedding = resp.output["embeddings"][0]["embedding"]
                    results[idx] = embedding
                    # ③ 写入缓存(30天过期，覆盖文本不变时的所有后续查询)
                    cache_key = f"emb:{self.model}:{text}"
                    cache_manager.set(cache_key, embedding, ttl=86400 * 30)
                else:
                    # API 失败直接抛异常，让上层(pipeline)的 try/except 兜底处理
                    raise RuntimeError(f"百炼 Embedding API 错误: {resp.code} - {resp.message}")

        return results

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        嵌入文档列表 — LangChain 接口。

        入库时调用: 把一批文档 chunk 一次性嵌入并写入 ChromaDB。
        参数是 List[str]，返回 List[List[float]]，每个内层列表是 1536 维的向量。
        """
        return self._embed_texts(texts)

    def embed_query(self, text: str) -> List[float]:
        """
        嵌入查询文本 — LangChain 接口。

        用户提问时调用: 把单个问题转成向量，用于在 ChromaDB 中做语义搜索。
        注意返回值不是 List[List[float]]，而是 List[float](单条)，
        这是 LangChain 契约的要求——单个查询永远只返回一个向量。
        """
        return self._embed_texts([text])[0]
