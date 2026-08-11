"""
RAG 测试 — 主流水线 (backend/rag/pipeline.py)

使用 mock 组件测试完整 RAG 问答链路，不调用真实 API。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestRAGPipelineQuery:
    """RAG 问答流水线"""

    @pytest.fixture
    def mock_deps(self, monkeypatch):
        """Mock pipeline 的所有底层依赖，使其不触发真实 ChromaDB / API 调用"""
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_scores.return_value = [
            {
                "content": "iPhone 15 Pro Max 售价 ¥9,999 起。",
                "filename": "apple.txt",
                "doc_id": "d001",
                "chunk_index": 0,
                "score": 0.95,
            },
            {
                "content": "华为 Mate 60 Pro 支持卫星通话，售价 ¥6,999 起。",
                "filename": "huawei.txt",
                "doc_id": "d002",
                "chunk_index": 1,
                "score": 0.88,
            },
        ]

        mock_llm = MagicMock()
        mock_llm.stream.return_value = iter([
            "根据知识库内容，iPhone 15 Pro Max 售价为 ¥9,999 起。",
        ])

        # 替换全局单例
        from backend.rag import pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "_retriever", mock_retriever)
        monkeypatch.setattr(pipeline_mod, "_llm", mock_llm)
        # 清除缓存避免干扰
        from backend.cache.cache_manager import cache_manager
        cache_manager.clear()

        return {"retriever": mock_retriever, "llm": mock_llm}

    @pytest.mark.asyncio
    async def test_query_yields_sources_first(self, mock_deps):
        """问题改写后应立即返回 sources"""
        from backend.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()
        pipeline._do_retrieve = mock_deps["retriever"].retrieve_with_scores

        events = []
        async for event in pipeline.query(kb_id="kb-test", question="iPhone 多少钱？"):
            events.append(event)

        assert len(events) >= 2
        assert events[0]["type"] == "rewrite"
        assert events[1]["type"] == "sources"

    @pytest.mark.asyncio
    async def test_query_yields_tokens(self, mock_deps):
        """sources 之后应该流式输出 token"""
        from backend.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()
        pipeline._do_retrieve = mock_deps["retriever"].retrieve_with_scores

        events = []
        async for event in pipeline.query(kb_id="kb-test", question="测试问题"):
            events.append(event)

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) > 0
        # 拼接 token 应包含关键信息
        full_answer = "".join([e["content"] for e in token_events])
        assert "¥9,999" in full_answer

    @pytest.mark.asyncio
    async def test_query_ends_with_done(self, mock_deps):
        """最后一个事件应该是 done"""
        from backend.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()
        pipeline._do_retrieve = mock_deps["retriever"].retrieve_with_scores

        events = []
        async for event in pipeline.query(kb_id="kb-test", question="测试"):
            events.append(event)

        last_event = events[-1]
        assert last_event["type"] == "done"
        assert "metadata" in last_event
        assert "total_tokens" in last_event["metadata"]
        assert "latency_ms" in last_event["metadata"]

    @pytest.mark.asyncio
    async def test_query_no_sources(self, mock_deps):
        """无检索结果时给出友好提示"""
        mock_deps["retriever"].retrieve_with_scores.return_value = []

        from backend.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()
        pipeline._do_retrieve = mock_deps["retriever"].retrieve_with_scores

        events = []
        async for event in pipeline.query(kb_id="kb-empty", question="无答案问题"):
            events.append(event)

        token_events = [e for e in events if e["type"] == "token"]
        full = "".join([e["content"] for e in token_events])
        assert "暂未收录" in full or "抱歉" in full or "知识库" in full

    @pytest.mark.asyncio
    async def test_query_rewrites_follow_up_with_history(self, mock_deps, monkeypatch):
        from backend.rag.pipeline import RAGPipeline

        mock_deps["llm"].invoke.return_value = "iPhone 15 Pro Max 支持多大功率快充？"
        pipeline = RAGPipeline()
        pipeline._do_retrieve = mock_deps["retriever"].retrieve_with_scores
        history = [{"role": "user", "content": "iPhone 15 Pro Max 多少钱？"}]

        events = []
        async for event in pipeline.query("kb-test", "那它支持多大功率快充？", history=history):
            events.append(event)

        assert events[0]["type"] == "rewrite"
        assert "iPhone 15 Pro Max" in events[0]["rewritten_question"]
        called_query = mock_deps["retriever"].retrieve_with_scores.call_args.args[1]
        assert "iPhone 15 Pro Max" in called_query


class TestRAGPipelineIngest:
    """文档入库流水线"""

    @pytest.mark.asyncio
    async def test_ingest_success(self, monkeypatch, tmp_path):
        """模拟文档入库成功"""
        # 创建临时测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("这是一个测试文档。内容包含电商商品信息。" * 20, encoding="utf-8")

        # Mock RAGPipeline 的依赖
        from backend.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()

        # Mock embedding (在 vs_manager 中会用到)
        pipeline.embedding = MagicMock()

        # Mock vs_manager.add_documents
        pipeline.vs_manager = MagicMock()
        pipeline.vs_manager.add_documents = MagicMock()

        result = await pipeline.ingest_document(
            file_path=str(test_file),
            filename="test.txt",
            kb_id="kb-test",
            doc_id="ingest-test-001",
        )

        assert result["status"] == "completed"
        assert "chunk_count" in result
        assert result["chunk_count"] > 0
