"""
RAG 测试 — 文档加载器 (backend/rag/loader.py)

测试各种文件格式的加载能力（使用临时文件）。
"""
import pytest
from backend.rag.loader import DocumentLoader


class TestDocumentLoaderSupportedTypes:
    """支持的文档类型"""

    def test_supported_extensions(self):
        assert "pdf" in DocumentLoader.SUPPORTED_TYPES
        assert "docx" in DocumentLoader.SUPPORTED_TYPES
        assert "txt" in DocumentLoader.SUPPORTED_TYPES
        assert "md" in DocumentLoader.SUPPORTED_TYPES
        assert "csv" in DocumentLoader.SUPPORTED_TYPES
        assert "xlsx" in DocumentLoader.SUPPORTED_TYPES

    def test_unsupported_extension(self):
        """不支持的文件类型应抛出 ValueError"""
        with pytest.raises(ValueError, match="不支持的文件类型"):
            DocumentLoader.load("/fake/path/file.png")

    def test_unsupported_empty_ext(self):
        """没有后缀的文件应抛出 ValueError"""
        with pytest.raises(ValueError, match="不支持的文件类型"):
            DocumentLoader.load("/fake/path/noextfile")


class TestLoadTxt:
    """加载纯文本文件"""

    def test_load_txt(self, tmp_path):
        """加载 UTF-8 编码的 .txt 文件"""
        file_path = tmp_path / "sample.txt"
        file_path.write_text("这是第一行。\n这是第二行。\n这是第三行。", encoding="utf-8")

        docs = DocumentLoader.load(str(file_path))
        assert len(docs) >= 1
        # 文档应包含元数据
        for doc in docs:
            assert "filename" in doc.metadata
            assert doc.metadata["filename"] == "sample.txt"
            assert doc.metadata["file_type"] == "txt"

    def test_load_txt_content(self, tmp_path):
        """加载的内容应与原文相符"""
        content = "iPhone 15 Pro Max 起售价 ¥9,999"
        file_path = tmp_path / "apple.txt"
        file_path.write_text(content, encoding="utf-8")

        docs = DocumentLoader.load(str(file_path))
        combined = " ".join([d.page_content for d in docs])
        assert "iPhone" in combined


class TestLoadMd:
    """加载 Markdown 文件"""

    def test_load_md(self, tmp_path):
        """加载 .md 文件"""
        file_path = tmp_path / "readme.md"
        file_path.write_text("# 标题\n\n这是一段 Markdown 文本。\n\n- 列表项1\n- 列表项2", encoding="utf-8")

        docs = DocumentLoader.load(str(file_path))
        assert len(docs) >= 1
        for doc in docs:
            assert doc.metadata["file_type"] == "md"


class TestLoadCsv:
    """加载 CSV 文件"""

    def test_load_csv(self, tmp_path):
        """加载 CSV 文件"""
        file_path = tmp_path / "products.csv"
        file_path.write_text("名称,价格,类别\niPhone 15,¥9,999,手机\nMate 60,¥6,999,手机", encoding="utf-8")

        docs = DocumentLoader.load(str(file_path))
        assert len(docs) >= 1
        for doc in docs:
            assert doc.metadata["file_type"] == "csv"
