"""
检索器 — 语义 + 关键词 + MMR 多路召回与 RRF 重排

RAG 中的"R"(Retrieval)环节，负责从向量数据库中找到与用户问题最相关的文档片段。

检索策略选择: MMR (Maximal Marginal Relevance)
  - 为什么不用简单的语义相似度检索(similarity_search)?
    → 语义相似度只会返回最"相关"的结果，但在电商场景下可能全是同一个商品的 chunk
       (比如"iPhone 15"的前5个chunk都是同一份规格书的不同段落)
  - MMR 做了什么?
    → 在"相关性"和"多样性"之间取得平衡: 先从候选池(fetch_k=10)中选最相关的，
      然后每次迭代时优先选"与已选结果不太像但和问题仍然相关"的文档
  - lambda_mult=0.7 表示: 70%权重给相关性，30%给多样性
    → 偏向相关性: 因为电商问答中"准确性"比"覆盖面"更重要，
      用户问价格必须给出准确价格，不需要额外塞入不相关的商品介绍

去重策略: 基于内容前100字符哈希
  - 为什么不全文哈希? 效率——100字符已经足够区分不同chunk，全文多耗费CPU
  - 为什么不去重所有结果? 只在MMR返回结果中做轻量去重，保持检索速度
"""
import math
import re
from collections import Counter
from typing import List, Tuple
from langchain_core.documents import Document
from backend.rag.vector_store import VectorStoreManager


class RAGRetriever:
    """
    RAG 检索器: 语义、关键词、MMR 多路召回 + RRF 重排。

    提供两种检索接口:
      retrieve()            → 返回 LangChain Document 对象列表(用于后续 chain 组装)
      retrieve_with_scores() → 返回字典列表(用于前端展示"参考来源"面板，含分数)

    使用示例:
      retriever = RAGRetriever(vector_store_manager=vs_manager)
      docs = retriever.retrieve(kb_id="kb-1", query="iPhone价格", top_k=4)
    """

    def __init__(self, vector_store_manager: VectorStoreManager):
        """注入向量存储管理器，获取 ChromaDB 的连接和 collection"""
        self.vs = vector_store_manager

    def retrieve(self, kb_id: str, query: str, top_k: int = 4, fetch_k: int = 10) -> Tuple[List[Document], List[float]]:
        """
        检索相关文档片段。

        参数:
          kb_id:   知识库ID，决定查哪个 ChromaDB collection
          query:   用户原始问题
          top_k:   最终返回的文档数(默认4: 足够覆盖答案，又不让上下文过长)
          fetch_k: MMR的候选池大小(默认10: 在10个候选中选4个，兼顾多样性)

        返回:
          (docs, scores): docs 是去重后的 Document 列表，最多 top_k 个

        为什么 fetch_k > top_k?
          MMR 算法需要一个大一点的候选池来保证多样性。如果只从 top_k 个里选，就退化成了简单搜索。
          fetch_k = top_k * 2.5 ≈ 10，经验值，平衡了检索质量和向量数据库查询时间。
        """
        store = self.vs.get_store(kb_id)

        # MMR 检索 — lambda_mult=0.7 时相关性和多样性的折中效果最好(参考 LangChain 推荐值)
        docs = store.max_marginal_relevance_search(
            query=query,
            k=top_k,
            fetch_k=fetch_k,
            lambda_mult=0.7,
        )

        # 去重: 不同文档可能含有相似内容(如两个版本的产品手册)，前100字符相同视为重复
        # 为什么用 hash 而不是 ==? set + 字符串比较 O(n²)，哈希 O(n)
        seen_contents = set()
        unique_docs = []
        for doc in docs:
            content_hash = hash(doc.page_content[:100])
            if content_hash not in seen_contents:
                seen_contents.add(content_hash)
                unique_docs.append(doc)

        return unique_docs[:top_k]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        """同时保留英文/数字词和中文单字、双字词，适合商品型号与中文描述。"""
        normalized = text.lower()
        latin = re.findall(r"[a-z0-9][a-z0-9.+-]*", normalized)
        chinese = re.findall(r"[\u4e00-\u9fff]", normalized)
        bigrams = ["".join(chinese[i:i + 2]) for i in range(len(chinese) - 1)]
        return latin + chinese + bigrams

    @classmethod
    def _bm25_scores(cls, query: str, documents: list[str]) -> list[float]:
        """无额外依赖的轻量 BM25，用于精确关键词召回。"""
        tokenized = [cls._tokens(doc) for doc in documents]
        query_tokens = set(cls._tokens(query))
        if not query_tokens or not tokenized:
            return [0.0] * len(documents)
        avg_len = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
        doc_freq = Counter(token for tokens in tokenized for token in set(tokens))
        scores = []
        for tokens in tokenized:
            counts = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                if not counts[token]:
                    continue
                idf = math.log(1 + (len(tokenized) - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
                tf = counts[token]
                denominator = tf + 1.5 * (1 - 0.75 + 0.75 * len(tokens) / max(avg_len, 1))
                score += idf * (tf * 2.5 / denominator)
            scores.append(score)
        return scores

    def retrieve_with_scores(
        self, kb_id: str, query: str, top_k: int = 4, fetch_k: int = 12,
    ) -> List[dict]:
        """
        检索并返回带分数的文档列表(JSON 友好，供前端展示)。

        返回格式:
          [{"content": "...", "filename": "apple.txt", "doc_id": "d001",
            "chunk_index": 5, "score": 0.92}, ...]

        为什么分数要 round(score, 4)?
          前端展示 0.9234 比 0.9234567890123456 更友好。4位小数足够区分相似度差异。
        """
        store = self.vs.get_store(kb_id)
        semantic = store.similarity_search_with_relevance_scores(query, k=fetch_k)
        mmr_docs = store.max_marginal_relevance_search(
            query=query, k=min(top_k * 2, fetch_k), fetch_k=fetch_k, lambda_mult=0.7,
        )

        # 关键词检索直接读取当前知识库的文本，适合型号、金额和日期等精确查询。
        raw = store.get(include=["documents", "metadatas"])
        lexical_docs = []
        if isinstance(raw, dict):
            for content, metadata in zip(raw.get("documents") or [], raw.get("metadatas") or []):
                lexical_docs.append(Document(page_content=content or "", metadata=metadata or {}))
        lexical_scores = self._bm25_scores(query, [doc.page_content for doc in lexical_docs])
        lexical_ranked = [
            doc for score, doc in sorted(zip(lexical_scores, lexical_docs), key=lambda item: item[0], reverse=True)
            if score > 0
        ][:fetch_k]

        def key(doc: Document) -> str:
            return f"{doc.metadata.get('doc_id', '')}:{doc.metadata.get('chunk_index', '')}:{doc.page_content[:80]}"

        candidates = {}
        fused = Counter()
        channel_map = {}
        for channel, weight, ranked_docs in (
            ("semantic", 0.55, [doc for doc, _ in semantic]),
            ("keyword", 0.30, lexical_ranked),
            ("diversity", 0.15, mmr_docs),
        ):
            for rank, doc in enumerate(ranked_docs, 1):
                doc_key = key(doc)
                candidates[doc_key] = doc
                fused[doc_key] += weight / (60 + rank)
                channel_map.setdefault(doc_key, []).append(channel)

        ranked = sorted(candidates, key=lambda item: fused[item], reverse=True)[:top_k]
        max_score = max((fused[item] for item in ranked), default=1.0)
        results = []
        for doc_key in ranked:
            doc = candidates[doc_key]
            results.append({
                "content": doc.page_content,
                "filename": doc.metadata.get("filename", ""),
                "doc_id": doc.metadata.get("doc_id", ""),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "score": round(fused[doc_key] / max_score, 4),
                "matched_by": channel_map[doc_key],
            })
        return results
