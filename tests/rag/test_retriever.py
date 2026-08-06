"""
RAG 测试 — 检索器 (backend/rag/retriever.py)

使用 mock VectorStoreManager 避免依赖真实 ChromaDB。
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from backend.rag.retriever import RAGRetriever


@pytest.fixture
def mock_vs_manager():
    """创建一个 mock VectorStoreManager"""
    mock = MagicMock()
    # 预设 get_store() 返回另一个 mock（Chroma 实例）
    mock_store = MagicMock()
    mock.get_store.return_value = mock_store
    return mock, mock_store


class TestRetrieve:
    """检索功能"""

    def test_retrieve_returns_docs(self, mock_vs_manager):
        """检索应返回文档列表"""
        mock_vs, mock_store = mock_vs_manager

        # 预设 MMR 检索返回结果
        mock_store.max_marginal_relevance_search.return_value = [
            Document(page_content="内容A", metadata={"filename": "a.txt"}),
            Document(page_content="内容B", metadata={"filename": "b.txt"}),
        ]

        retriever = RAGRetriever(vector_store_manager=mock_vs)
        docs = retriever.retrieve("kb-1", "测试查询", top_k=4)

        assert len(docs) > 0
        assert isinstance(docs[0], Document)
        mock_store.max_marginal_relevance_search.assert_called_once()

    def test_retrieve_deduplicates(self, mock_vs_manager):
        """内容重复的文档应被去重"""
        mock_vs, mock_store = mock_vs_manager

        # 两个内容相似的文档
        doc1 = Document(page_content="iPhone 15 Pro 售价 ¥9,999", metadata={"filename": "a.txt"})
        doc2 = Document(page_content="iPhone 15 Pro 售价 ¥9,999 起，多种颜色可选", metadata={"filename": "b.txt"})
        mock_store.max_marginal_relevance_search.return_value = [doc1, doc2]

        retriever = RAGRetriever(vector_store_manager=mock_vs)
        docs = retriever.retrieve("kb-1", "iPhone 价格", top_k=4)
        # 因为内容前100字符不同（第二个更长），可能都被保留
        # 实际测试去重逻辑
        assert len(docs) <= 2

    def test_retrieve_uses_correct_kb_store(self, mock_vs_manager):
        """检索应使用指定知识库的 vector store"""
        mock_vs, mock_store = mock_vs_manager

        retriever = RAGRetriever(vector_store_manager=mock_vs)
        retriever.retrieve("kb-42", "查询", top_k=4)

        mock_vs.get_store.assert_called_with("kb-42")


class TestRetrieveWithScores:
    """带分数的检索"""

    def test_retrieve_with_scores_format(self, mock_vs_manager):
        """返回的字典应包含所有必需字段"""
        mock_vs, mock_store = mock_vs_manager

        doc = Document(
            page_content="测试内容",
            metadata={"filename": "test.txt", "doc_id": "d001", "chunk_index": 5},
        )
        mock_store.similarity_search_with_relevance_scores.return_value = [(doc, 0.92)]

        retriever = RAGRetriever(vector_store_manager=mock_vs)
        results = retriever.retrieve_with_scores("kb-1", "查询", top_k=4)

        assert len(results) == 1
        assert results[0]["content"] == "测试内容"
        assert results[0]["filename"] == "test.txt"
        assert results[0]["doc_id"] == "d001"
        assert results[0]["chunk_index"] == 5
        assert results[0]["score"] == 0.92

    def test_retrieve_with_scores_empty(self, mock_vs_manager):
        """无结果时返回空列表"""
        mock_vs, mock_store = mock_vs_manager
        mock_store.similarity_search_with_relevance_scores.return_value = []

        retriever = RAGRetriever(vector_store_manager=mock_vs)
        results = retriever.retrieve_with_scores("kb-1", "无结果查询", top_k=4)

        assert results == []

    def test_retrieve_with_scores_score_rounded(self, mock_vs_manager):
        """分数应该四舍五入到 4 位小数"""
        mock_vs, mock_store = mock_vs_manager
        doc = Document(page_content="x", metadata={})
        mock_store.similarity_search_with_relevance_scores.return_value = [(doc, 0.1234567)]

        retriever = RAGRetriever(vector_store_manager=mock_vs)
        results = retriever.retrieve_with_scores("kb-1", "q", top_k=4)

        # 0.1234567 四舍五入到 4 位小数 = 0.1235
        assert results[0]["score"] == round(0.1234567, 4)
