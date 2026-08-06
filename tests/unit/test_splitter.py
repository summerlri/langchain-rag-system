"""
单元测试 — 文本分割器 (backend/rag/splitter.py)
"""
import pytest
from langchain_core.documents import Document
from backend.rag.splitter import get_text_splitter, split_documents


class TestTextSplitter:
    """文本分割器配置"""

    def test_default_chunk_size(self):
        """默认 chunk_size 应该生效"""
        splitter = get_text_splitter()
        assert splitter._chunk_size == 500

    def test_custom_chunk_size(self):
        """自定义 chunk_size"""
        splitter = get_text_splitter(chunk_size=800, chunk_overlap=100)
        assert splitter._chunk_size == 800
        assert splitter._chunk_overlap == 100

    def test_chinese_separators_included(self):
        """分割器应该包含中文标点分隔符"""
        splitter = get_text_splitter()
        assert "。" in splitter._separators
        assert "；" in splitter._separators
        assert "，" in splitter._separators


class TestSplitDocuments:
    """文档分割功能"""

    def test_single_doc_split(self):
        """单个文档被分割成多个 chunk"""
        long_text = "第一段内容。" * 50 + "第二段内容。" * 50
        doc = Document(page_content=long_text, metadata={"filename": "test.txt"})
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1

    def test_short_doc_not_split(self):
        """短文档可能不被分割（内容小于 chunk_size）"""
        short_text = "只有一句话。"
        doc = Document(page_content=short_text, metadata={"filename": "short.txt"})
        chunks = split_documents([doc], chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 1

    def test_empty_doc(self):
        """空文档至少返回一个 chunk（或空列表）"""
        doc = Document(page_content="", metadata={"filename": "empty.txt"})
        chunks = split_documents([doc], chunk_size=500, chunk_overlap=50)
        # 空内容的分割结果取决于 RecursiveCharacterTextSplitter 的行为
        assert isinstance(chunks, list)

    def test_chunks_have_index_metadata(self):
        """分割后每个 chunk 应包含 chunk_index 元数据"""
        text = "AAA。" * 30 + "BBB。" * 30 + "CCC。" * 30
        doc = Document(page_content=text, metadata={"filename": "indexed.txt"})
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=20)
        for i, chunk in enumerate(chunks):
            assert "chunk_index" in chunk.metadata

    def test_chunks_preserve_original_metadata(self):
        """分割后的 chunk 应保留原始文档的元数据"""
        doc = Document(
            page_content="测试内容。" * 30,
            metadata={"filename": "meta_test.txt", "author": "test_author"},
        )
        chunks = split_documents([doc], chunk_size=200, chunk_overlap=20)
        for chunk in chunks:
            assert chunk.metadata["filename"] == "meta_test.txt"
            assert chunk.metadata["author"] == "test_author"

    def test_multiple_docs_split(self):
        """多个文档同时分割"""
        docs = [
            Document(page_content="文档一。" * 30, metadata={"filename": "doc1.txt"}),
            Document(page_content="文档二。" * 30, metadata={"filename": "doc2.txt"}),
        ]
        chunks = split_documents(docs, chunk_size=200, chunk_overlap=20)
        filenames = {c.metadata["filename"] for c in chunks}
        assert "doc1.txt" in filenames
        assert "doc2.txt" in filenames
